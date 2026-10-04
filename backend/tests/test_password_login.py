from __future__ import annotations

import uuid

import bcrypt
import pytest
import pytest_asyncio
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.domains.auth.router as auth_router
from app.core.auth.security import ALGORITHM, get_password_hash, verify_password, _require_secret_key

PASSWORD = "Correct-horse-9"


@pytest_asyncio.fixture(autouse=True)
def _reset_login_rate_limit():
    """로그인은 분당 5회 제한이 있어 테스트끼리 횟수가 누적되지 않게 초기화한다."""
    auth_router.limiter.reset()
    yield
    auth_router.limiter.reset()


async def _insert_password_user(
    session: AsyncSession, password_hash: str | None, *, is_active: bool = True, role: str = "CONTENT_MANAGER"
) -> tuple[uuid.UUID, str]:
    user_id = uuid.uuid4()
    username = f"pw-{user_id.hex[:8]}"
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role, password, feedback_consent)
            values (:id, :username, :email, :display_name, :is_active, 'ACTIVE', :role, :password, true)
            """
        ),
        {
            "id": str(user_id),
            "username": username,
            "email": f"{username}@example.com",
            "display_name": username,
            "is_active": is_active,
            "role": role,
            "password": password_hash,
        },
    )
    await session.commit()
    return user_id, username


# ── 해시·검증 ─────────────────────────────────────────────────

def test_hash_and_verify():
    hashed = get_password_hash(PASSWORD)
    assert hashed.startswith("$2b$")
    assert hashed != PASSWORD
    assert verify_password(PASSWORD, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_accepts_existing_2a_hashes():
    """예전 라이브러리(passlib)로 저장된 bcrypt 해시 형식도 그대로 검증된다."""
    hashed_2a = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(prefix=b"2a")).decode()
    assert hashed_2a.startswith("$2a$")
    assert verify_password(PASSWORD, hashed_2a) is True


@pytest.mark.parametrize("stored", [None, "", "not-a-bcrypt-hash"])
def test_verify_without_valid_hash_is_false(stored):
    assert verify_password(PASSWORD, stored) is False


def test_verify_too_long_password_is_false():
    assert verify_password("a" * 73, get_password_hash(PASSWORD)) is False


# ── 계정 생성 ─────────────────────────────────────────────────

async def test_admin_creates_user_with_hashed_password(admin_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    username = f"new-{uuid.uuid4().hex[:8]}"
    res = await admin_client.post("/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "display_name": "새 매니저",
        "password": PASSWORD,
        "role": "CONTENT_MANAGER",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "CONTENT_MANAGER"
    assert "password" not in body

    async with db_conn_and_sessionmaker() as session:
        stored = (await session.execute(text("select password from public.users where id = :id"), {"id": body["id"]})).scalar_one()
    assert stored != PASSWORD
    assert verify_password(PASSWORD, stored) is True


async def test_create_user_rejects_password_over_72_bytes(admin_client):
    username = f"long-{uuid.uuid4().hex[:8]}"
    res = await admin_client.post("/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "display_name": "긴 비밀번호",
        "password": "가" * 25,  # 한글 25자 = 75바이트
    })
    assert res.status_code == 422, res.text


# ── 로그인 ────────────────────────────────────────────────────

async def test_login_issues_token(admin_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    async with db_conn_and_sessionmaker() as session:
        user_id, username = await _insert_password_user(session, get_password_hash(PASSWORD))

    res = await admin_client.post("/auth/login", data={"username": username, "password": PASSWORD})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "CONTENT_MANAGER"
    claims = jwt.decode(body["access_token"], _require_secret_key(), algorithms=[ALGORITHM])
    assert claims["sub"] == str(user_id)


@pytest.mark.parametrize(
    "password_hash, is_active, login_password",
    [
        ("HASH", True, "wrong-password"),   # 비밀번호 불일치
        ("HASH", False, PASSWORD),          # 비활성 계정
        (None, True, PASSWORD),             # 비밀번호 없이 만들어진 계정 (Supabase 로그인 사용자)
        ("HASH", True, "a" * 100),          # 72바이트 초과 입력
    ],
)
async def test_login_rejected_with_400(
    admin_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession], password_hash, is_active, login_password
):
    stored = get_password_hash(PASSWORD) if password_hash == "HASH" else None
    async with db_conn_and_sessionmaker() as session:
        _, username = await _insert_password_user(session, stored, is_active=is_active)

    res = await admin_client.post("/auth/login", data={"username": username, "password": login_password})
    assert res.status_code == 400, res.text


async def test_login_unknown_user_is_400(admin_client):
    res = await admin_client.post("/auth/login", data={"username": "nobody-here", "password": PASSWORD})
    assert res.status_code == 400, res.text


async def test_login_rate_limit(admin_client):
    codes = [
        (await admin_client.post("/auth/login", data={"username": "nobody-here", "password": "x"})).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429


async def test_old_login_path_is_gone(admin_client):
    """로그인은 /auth/login 으로 옮겼다 (예전 /users/login/access-token 없음)."""
    res = await admin_client.post("/users/login/access-token", data={"username": "x", "password": "x"})
    assert res.status_code in (404, 405), res.text
