from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from typing import Optional, Any
from urllib.parse import unquote
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import jwt as jose_jwt
from jose.exceptions import JWTError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.core.auth.supabase_jwt import (
    SupabaseJWTError,
    SupabaseJWTExpired,
    verify_supabase_access_token,
)
from app.domains.users.models import User
from app.security import SECRET_KEY as LOCAL_SECRET_KEY, ALGORITHM as LOCAL_ALGORITHM

bearer = HTTPBearer(auto_error=False)
bearer_optional = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]
    phone: Optional[str]
    username: str
    display_name: str
    role: str
    status: str
    is_active: bool


# Utilities: token 파싱
def _parse_sub_to_uuid(sub: str | None) -> UUID:
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")
    try:
        return UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token: malformed sub")


def _make_username(user_id: UUID, email: str | None) -> str:
    base = (email.split("@")[0] if email else f"user_{str(user_id)[:8]}")
    return base[:30]


def _maybe_b64decode(s: str) -> str:
    """
    Supabase auth cookie는 환경/버전에 따라 base64- prefix 또는 URL 인코딩이 섞일 수 있어
    최대한 관대하게 디코딩한다.
    """
    s = s.strip()
    if s.startswith("base64-"):
        b64 = s[len("base64-") :]
        pad = "=" * (-len(b64) % 4)
        try:
            return base64.urlsafe_b64decode((b64 + pad).encode("utf-8")).decode("utf-8")
        except Exception:
            return s
    return s


def _extract_access_token_from_supabase_cookie_value(raw: str) -> Optional[str]:
    """
    sb-*-auth-token 쿠키 값에서 access_token 추출
    - 쿠키 값이 JSON 또는 JSON이 base64/url-encoded인 케이스가 많음
    """
    if not raw:
        return None

    val = unquote(raw)
    val = _maybe_b64decode(val)

    # express cookie 처럼 "j:" prefix 있을 수 있음
    if val.startswith("j:"):
        val = val[2:]

    try:
        obj: Any = json.loads(val)
    except Exception:
        return None

    def pick(d: Any) -> Optional[str]:
        if isinstance(d, dict):
            if isinstance(d.get("access_token"), str):
                return d["access_token"]
            # nested 형태 대응
            for k in ("currentSession", "session", "data"):
                v = d.get(k)
                if isinstance(v, dict) and isinstance(v.get("access_token"), str):
                    return v["access_token"]
        if isinstance(d, list) and d:
            first = d[0]
            if isinstance(first, dict) and isinstance(first.get("access_token"), str):
                return first["access_token"]
        return None

    return pick(obj)


def _get_supabase_cookie_access_token(request: Request) -> Optional[str]:
    """
    쿠키 중 sb-*-auth-token 패턴을 찾아 access_token만 뽑아낸다.
    (Authorization 헤더가 정상적으로 온다면 이건 보험 역할)
    """
    for name, value in request.cookies.items():
        if name.startswith("sb-") and name.endswith("-auth-token"):
            token = _extract_access_token_from_supabase_cookie_value(value)
            if token:
                return token
    return None

# Token verification
def _verify_local_hs256_token(token: str) -> dict:
    """
    (옵션) /users/login/access-token 등에서 발급한 로컬 HS256 JWT 검증
    - 현재 프론트는 Supabase를 쓰지만, “간섭 최소/전환 대비”로 fallback 유지
    """
    if not LOCAL_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jose_jwt.decode(token, LOCAL_SECRET_KEY, algorithms=[LOCAL_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    return payload


async def verify_any_access_token(token: str) -> dict:
    """
    - Supabase access token 검증 시도
    - 실패하면 로컬 HS256 검증 시도(옵션)
    """
    try:
        return await verify_supabase_access_token(
            token=token,
            supabase_url=settings.SUPABASE_URL,
            jwt_secret=getattr(settings, "SUPABASE_JWT_SECRET", None),
            issuer_override=getattr(settings, "SUPABASE_JWT_ISSUER", None),
            audience=getattr(
                settings,
                "SUPABASE_JWT_AUDIENCE",
                getattr(settings, "SUPABASE_JWT_AUD", "authenticated"),
            ),
        )
    except SupabaseJWTExpired:
        raise HTTPException(status_code=401, detail="Token expired")
    except SupabaseJWTError:
        return _verify_local_hs256_token(token)


# Access token acquisition
async def get_access_token_optional(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
) -> Optional[str]:
    # Authorization: Bearer 우선
    if cred and cred.scheme.lower() == "bearer":
        return cred.credentials

    # Supabase cookie에서 access_token 추출
    token = _get_supabase_cookie_access_token(request)
    if token:
        return token

    return None


async def get_access_token(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    # Authorization: Bearer 우선
    if cred and cred.scheme.lower() == "bearer":
        return cred.credentials

    # Supabase cookie에서 access_token 추출
    token = _get_supabase_cookie_access_token(request)
    if token:
        return token

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")


async def get_claims_optional(
    token: Optional[str] = Depends(get_access_token_optional),
) -> Optional[dict]:
    if not token:
        return None
    return await verify_any_access_token(token)


async def get_claims(token: str = Depends(get_access_token)) -> dict:
    return await verify_any_access_token(token)


# Super admin bootstrap
async def _maybe_bootstrap_super_admin(
    *,
    user: User,
    claims: dict,
    session: AsyncSession,
) -> User:
    """
    부트스트랩 규칙:
    - settings.SUPER_ADMIN_USER_ID == user.id 이거나
    - settings.SUPER_ADMIN_EMAIL == claims.email (또는 user.email) 이면
      -> user.role=ADMIN, user.status=ACTIVE, user.is_active=True 로 강제 승격
    - 이미 ADMIN이면 아무것도 안 함
    """
    target_id = (getattr(settings, "SUPER_ADMIN_USER_ID", None) or "").strip()
    target_email = (getattr(settings, "SUPER_ADMIN_EMAIL", None) or "").strip().lower()

    claim_email = (claims.get("email") or "").strip().lower()
    user_email = ((user.email or "")).strip().lower()

    is_match = False
    if target_id and str(user.id) == target_id:
        is_match = True
    if target_email and (claim_email == target_email or user_email == target_email):
        is_match = True

    if not is_match:
        return user

    if (user.role or "").strip().upper() == "ADMIN":
        return user

    user.role = "ADMIN"
    user.status = "ACTIVE"
    user.is_active = True

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# Current user provisioning (JIT)
async def _get_or_create_user_from_claims(
    claims: dict,
    session: AsyncSession,
) -> CurrentUser:
    sub = claims.get("sub")
    email = claims.get("email")
    phone = claims.get("phone")

    user_uuid = _parse_sub_to_uuid(sub)

    # 조회
    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    # JIT 생성
    if user is None:
        username_base = _make_username(user_uuid, email)
        display_name = (claims.get("user_metadata", {}) or {}).get("full_name")
        display = display_name or email or phone or "사용자"

        for i in range(5):
            suffix = "" if i == 0 else "_" + secrets.token_hex(2)
            username = (username_base + suffix)[:40]

            new_user = User(
                id=user_uuid,
                username=username,
                email=email,
                display_name=display,
                role="CUSTOMER",
                status="ACTIVE",
                is_active=True,
                password=None,
            )
            session.add(new_user)

            try:
                await session.commit()
                await session.refresh(new_user)
                user = new_user
                break
            except IntegrityError:
                await session.rollback()
                # 동시에 생성된 경우 재조회
                result = await session.execute(select(User).where(User.id == user_uuid))
                existing = result.scalar_one_or_none()
                if existing is not None:
                    user = existing
                    break

        if user is None:
            raise HTTPException(status_code=500, detail="Failed to provision user")

    # super admin bootstrap (user 확정 후)
    user = await _maybe_bootstrap_super_admin(user=user, claims=claims, session=session)

    # CurrentUser 반환(정규화)
    role = ((user.role or "CUSTOMER").strip()).upper()
    acc_status = ((getattr(user, "status", "ACTIVE") or "ACTIVE").strip()).upper()
    active_flag = bool(getattr(user, "is_active", True))

    return CurrentUser(
        id=str(user.id),
        email=user.email,
        phone=phone,
        username=user.username,
        display_name=user.display_name,
        role=role,
        status=acc_status,
        is_active=active_flag,
    )


async def get_current_user_optional(
    claims: Optional[dict] = Depends(get_claims_optional),
    session: AsyncSession = Depends(get_session),
) -> Optional[CurrentUser]:
    if claims is None:
        return None
    return await _get_or_create_user_from_claims(claims, session)


async def get_current_user(
    claims: dict = Depends(get_claims),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    return await _get_or_create_user_from_claims(claims, session)


oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


# Guards
def require_role(allowed_roles: set[str]):
    """
    - is_active=False → 전 역할 차단
    - status=SUSPENDED → 차단
    - INSTRUCTOR/CONTENT_MANAGER는 status=ACTIVE 아니면 차단(승인 대기)
    """
    allowed = {r.strip().upper() for r in allowed_roles}

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Inactive account")

        role = (user.role or "").strip().upper()
        acc_status = (user.status or "ACTIVE").strip().upper()

        if role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")

        if acc_status == "SUSPENDED":
            raise HTTPException(status_code=403, detail="Suspended account")

        if role in {"INSTRUCTOR", "CONTENT_MANAGER"} and acc_status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Approval pending")

        return user

    return _guard


async def _is_staff_of_instructor(
    session: AsyncSession,
    *,
    instructor_id: str,
    staff_user_id: str,
) -> bool:
    res = await session.execute(
        text(
            """
            select 1
            from public.instructor_staff
            where instructor_id = :instructor_id
              and staff_user_id = :staff_user_id
            limit 1
            """
        ),
        {"instructor_id": instructor_id, "staff_user_id": staff_user_id},
    )
    return res.first() is not None


def require_instructor_or_staff(instructor_id: str):
    async def _guard(
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> CurrentUser:
        role = (user.role or "").upper()

        if role == "ADMIN":
            return user

        if role == "INSTRUCTOR" and str(user.id) == str(instructor_id):
            return user

        if role == "CONTENT_MANAGER":
            ok = await _is_staff_of_instructor(
                session,
                instructor_id=str(instructor_id),
                staff_user_id=str(user.id),
            )
            if ok:
                return user

        raise HTTPException(status_code=403, detail="Insufficient role")

    return _guard