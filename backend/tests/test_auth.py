"""인증: 토큰 검증(Supabase 형식 → 실패 시 로컬 HS256 폴백), 최초 로그인 유저 생성(JIT), 역할 확인

다른 테스트와 달리 get_current_user 를 바꿔 끼우지 않고 실제 토큰을 붙여 호출한다.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.auth.supabase_jwt as supabase_jwt
from app.core.auth.security import _require_secret_key
from app.core.config import settings
from app.db.session import get_session
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def raw_client(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession], monkeypatch) -> AsyncIterator[AsyncClient]:
    """DB 세션만 테스트용으로 바꾸고 인증은 실제 경로를 탄다. JWKS 는 네트워크 없이 빈 목록."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as session:
            yield session

    async def no_network_jwks(url: str) -> dict:
        return {"keys": []}

    monkeypatch.setattr(supabase_jwt, "_fetch_jwks", no_network_jwks)
    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def supabase_token(sub: str, email: str | None = None, *, exp_in: int = 600, **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": sub,
        "email": email,
        "aud": settings.SUPABASE_JWT_AUDIENCE,
        "iss": settings.SUPABASE_ISSUER,
        "iat": now,
        "exp": now + exp_in,
    }
    secret = overrides.pop("secret", settings.SUPABASE_JWT_SECRET)
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def local_token(sub: str, *, exp_in: int = 600) -> str:
    return jwt.encode({"sub": sub, "exp": int(time.time()) + exp_in}, _require_secret_key(), algorithm="HS256")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


async def _insert_user(session: AsyncSession, *, role: str = "CUSTOMER", status: str = "ACTIVE", is_active: bool = True, email: str | None = None) -> uuid.UUID:
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role, feedback_consent)
            values (:id, :username, :email, 'auth-test', :is_active, :status, :role, true)
            """
        ),
        {
            "id": str(user_id),
            "username": f"auth-{user_id.hex[:8]}",
            "email": email or f"auth-{user_id.hex[:8]}@example.com",
            "is_active": is_active,
            "status": status,
            "role": role,
        },
    )
    await session.commit()
    return user_id


# ── 거부되는 토큰 ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "make_headers",
    [
        lambda: {},                                                          # 토큰 없음
        lambda: bearer("not-a-jwt"),                                         # 형식 오류
        lambda: bearer(supabase_token(str(uuid.uuid4()), aud="other")),      # audience 불일치
        lambda: bearer(supabase_token(str(uuid.uuid4()), iss="https://evil.example/auth/v1")),  # issuer 불일치
        lambda: bearer(supabase_token(str(uuid.uuid4()), secret="wrong-secret-wrong-secret-0000")),  # 다른 키
        lambda: bearer(_b64({"alg": "none", "typ": "JWT"}) + "." + _b64({"sub": str(uuid.uuid4()), "exp": int(time.time()) + 600}) + "."),
        lambda: bearer(_b64({"alg": "RS256", "kid": "unknown"}) + "." + _b64({"sub": str(uuid.uuid4())}) + "." + _b64({"x": 1})),
        lambda: bearer(supabase_token("not-a-uuid")),                        # sub 형식 오류
        lambda: bearer(local_token(str(uuid.uuid4()), exp_in=-60)),          # 만료된 로컬 토큰
    ],
    ids=["none", "malformed", "aud", "iss", "wrong-key", "alg-none", "rs256-unknown-kid", "bad-sub", "local-expired"],
)
async def test_invalid_tokens_are_401(raw_client, make_headers):
    r = await raw_client.get("/auth/me", headers=make_headers())
    assert r.status_code == 401, r.text


async def test_expired_supabase_token_says_expired(raw_client):
    r = await raw_client.get("/auth/me", headers=bearer(supabase_token(str(uuid.uuid4()), exp_in=-60)))
    assert r.status_code == 401
    assert "expired" in r.text.lower()


# ── 최초 로그인 유저 생성 (JIT) ───────────────────────────────

async def test_first_login_creates_customer_once(raw_client, db_conn_and_sessionmaker):
    sub = str(uuid.uuid4())
    email = f"jit-{sub[:8]}@example.com"
    for _ in range(2):
        r = await raw_client.get("/auth/me", headers=bearer(supabase_token(sub, email)))
        assert r.status_code == 200, r.text
        assert r.json()["id"] == sub and r.json()["role"] == "CUSTOMER"

    async with db_conn_and_sessionmaker() as session:
        count = (await session.execute(text("select count(*) from public.users where id = :id"), {"id": sub})).scalar_one()
    assert count == 1


async def test_super_admin_email_is_promoted(raw_client, monkeypatch):
    email = f"boss-{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(settings, "SUPER_ADMIN_EMAIL", email)
    r = await raw_client.get("/auth/me", headers=bearer(supabase_token(str(uuid.uuid4()), email)))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ADMIN"


async def test_email_used_by_another_account_is_409(raw_client, db_conn_and_sessionmaker):
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    async with db_conn_and_sessionmaker() as session:
        await _insert_user(session, email=email)

    # 같은 이메일, 다른 Supabase 계정 id
    r = await raw_client.get("/auth/me", headers=bearer(supabase_token(str(uuid.uuid4()), email)))
    assert r.status_code == 409, r.text


# ── 로컬 HS256 폴백 ───────────────────────────────────────────

async def test_local_fallback_token_is_accepted(raw_client, db_conn_and_sessionmaker):
    async with db_conn_and_sessionmaker() as session:
        user_id = await _insert_user(session, role="CONTENT_MANAGER")
    r = await raw_client.get("/auth/me", headers=bearer(local_token(str(user_id))))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "CONTENT_MANAGER"


# ── 역할 확인 (require_role) ──────────────────────────────────

@pytest.mark.parametrize(
    "role, status, is_active, expected",
    [
        ("CUSTOMER", "ACTIVE", True, 403),        # 역할 부족
        ("INSTRUCTOR", "PENDING", True, 403),     # 승인 대기
        ("INSTRUCTOR", "SUSPENDED", True, 403),   # 정지
        ("INSTRUCTOR", "ACTIVE", False, 403),     # 비활성 계정
        ("INSTRUCTOR", "ACTIVE", True, 404),      # 통과 (캘린더가 없어 404)
    ],
)
async def test_role_guard(raw_client, db_conn_and_sessionmaker, role, status, is_active, expected):
    async with db_conn_and_sessionmaker() as session:
        user_id = await _insert_user(session, role=role, status=status, is_active=is_active)
    r = await raw_client.get("/calendars/me/time-slots", headers=bearer(supabase_token(str(user_id))))
    assert r.status_code == expected, r.text


# ── 설정: 발급자(iss)·대상(aud) 지정 ───────────────────────────

async def test_custom_issuer_and_audience_are_used(raw_client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", "https://auth.example.com/auth/v1/")
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "my-app")
    sub = str(uuid.uuid4())
    ok = supabase_token(sub, f"iss-{sub[:8]}@example.com", iss="https://auth.example.com/auth/v1", aud="my-app")
    assert (await raw_client.get("/auth/me", headers=bearer(ok))).status_code == 200
    # 기본 발급자·대상으로 만든 토큰은 이제 거부
    default_iss = settings.SUPABASE_URL.rstrip("/") + "/auth/v1"
    assert (await raw_client.get("/auth/me", headers=bearer(supabase_token(sub, iss=default_iss, aud="my-app")))).status_code == 401
    assert (await raw_client.get("/auth/me", headers=bearer(supabase_token(sub, iss="https://auth.example.com/auth/v1", aud="authenticated")))).status_code == 401


async def test_settings_read_issuer_and_old_audience_name(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "https://auth.example.com/auth/v1")
    monkeypatch.delenv("SUPABASE_JWT_AUDIENCE", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_AUD", "legacy-aud")
    s = Settings(_env_file=None)
    assert s.SUPABASE_ISSUER == "https://auth.example.com/auth/v1"
    assert s.SUPABASE_JWT_AUDIENCE == "legacy-aud"

    monkeypatch.delenv("SUPABASE_JWT_ISSUER")
    assert Settings(_env_file=None).SUPABASE_ISSUER == s.SUPABASE_URL.rstrip("/") + "/auth/v1"


async def test_withdrawn_account_cannot_log_in(raw_client, db_conn_and_sessionmaker):
    async with db_conn_and_sessionmaker() as session:
        user_id = await _insert_user(session, status="WITHDRAWN", is_active=False)
    r = await raw_client.get("/auth/me", headers=bearer(supabase_token(str(user_id))))
    assert r.status_code == 403 and "탈퇴" in r.text

