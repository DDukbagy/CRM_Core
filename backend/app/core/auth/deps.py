from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
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
from app.domains.users.models import User  # ✅ ORM 기반 JIT용

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]
    phone: Optional[str]
    username: str
    display_name: str
    role: str


bearer_optional = HTTPBearer(auto_error=False)


async def get_access_token_optional(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
) -> Optional[str]:
    if not cred or cred.scheme.lower() != "bearer":
        return None
    return cred.credentials


async def get_claims_optional(
    token: Optional[str] = Depends(get_access_token_optional),
) -> Optional[dict]:
    if not token:
        return None
    try:
        return await verify_supabase_access_token(
            token=token,
            supabase_url=settings.SUPABASE_URL,
            jwt_secret=getattr(settings, "SUPABASE_JWT_SECRET", None),
            issuer_override=getattr(settings, "SUPABASE_JWT_ISSUER", None),
            audience=getattr(settings, "SUPABASE_JWT_AUD", "authenticated"),
        )
    except SupabaseJWTExpired:
        # optional이라도 "잘못된 토큰"은 401로 막는 게 운영상 안전
        raise HTTPException(status_code=401, detail="Token expired")
    except SupabaseJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _parse_sub_to_uuid(sub: str | None) -> UUID:
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")
    try:
        return UUID(str(sub))
    except (ValueError, TypeError):
        # ✅ sub가 UUID가 아니면 500이 아니라 401
        raise HTTPException(status_code=401, detail="Invalid token: malformed sub")


def _make_username(user_id: UUID, email: str | None) -> str:
    """
    자동 생성 username 규칙
    - email이 있으면 email prefix 우선
    - 없으면 user_<uuid앞8자리>
    - DB 제약: max_length 40, unique
    """
    base = (email.split("@")[0] if email else f"user_{str(user_id)[:8]}")
    # 너무 길어지면 suffix 붙일 여지를 남기기 위해 base는 30자로 제한
    return base[:30]


async def _get_or_create_user_from_claims(
    claims: dict,
    session: AsyncSession,
) -> CurrentUser:
    """
    claims -> CurrentUser (JIT 포함)
    get_current_user / get_current_user_optional이 동일 로직을 공유한다.

    ✅ 변경점(인증 안정화):
    - sub(UUID) 검증 실패는 401로 귀결
    - users row가 없으면 ORM 기반으로 안전하게 생성(JIT)
    - username unique 충돌/동시성은 IntegrityError 처리 후 재조회/재시도
    """
    sub = claims.get("sub")
    email = claims.get("email")
    phone = claims.get("phone")

    user_uuid = _parse_sub_to_uuid(sub)

    # 1) 먼저 조회
    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    # 2) 없으면 JIT 생성
    if user is None:
        username_base = _make_username(user_uuid, email)
        display_name = (claims.get("user_metadata", {}) or {}).get("full_name")  # 있으면 참고
        display = display_name or email or phone or "사용자"

        for i in range(5):
            suffix = "" if i == 0 else "_" + secrets.token_hex(2)  # 4 hex
            username = (username_base + suffix)[:40]

            new_user = User(
                id=user_uuid,
                username=username,
                email=email,
                display_name=display,
                role="CUSTOMER",
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

                # 동시성으로 누군가 먼저 만들었으면 재조회해서 사용
                result = await session.execute(select(User).where(User.id == user_uuid))
                existing = result.scalar_one_or_none()
                if existing is not None:
                    user = existing
                    break

        if user is None:
            raise HTTPException(status_code=500, detail="Failed to provision user")

    # 3) CurrentUser로 반환 (role/display_name은 NOT NULL 전제로 유지)
    return CurrentUser(
        id=str(user.id),
        email=user.email,
        phone=phone,
        username=user.username,
        display_name=user.display_name,
        role=(user.role or "CUSTOMER"),
    )


async def get_current_user_optional(
    claims: Optional[dict] = Depends(get_claims_optional),
    session: AsyncSession = Depends(get_session),
) -> Optional[CurrentUser]:
    if claims is None:
        return None
    return await _get_or_create_user_from_claims(claims, session)


oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_access_token(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if not cred or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return cred.credentials


async def get_claims(token: str = Depends(get_access_token)) -> dict:
    try:
        return await verify_supabase_access_token(
            token=token,
            supabase_url=settings.SUPABASE_URL,
            jwt_secret=getattr(settings, "SUPABASE_JWT_SECRET", None),
            issuer_override=getattr(settings, "SUPABASE_JWT_ISSUER", None),
            audience=getattr(settings, "SUPABASE_JWT_AUD", "authenticated"),
        )
    except SupabaseJWTExpired:
        raise HTTPException(status_code=401, detail="Token expired")
    except SupabaseJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    claims: dict = Depends(get_claims),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    운영형 JIT 프로비저닝:
    - Supabase sub(UUID)를 우리 public.users.id로 사용
    - 없으면 자동 생성 (display_name NOT NULL 대응)
    """
    return await _get_or_create_user_from_claims(claims, session)


def require_role(allowed_roles: set[str]):
    allowed = {r.upper() for r in allowed_roles}

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if (user.role or "").upper() not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
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

        # ADMIN은 항상 허용
        if role == "ADMIN":
            return user

        # 강사 본인 허용
        if role == "INSTRUCTOR" and str(user.id) == str(instructor_id):
            return user

        # 콘텐츠 매니저는 위임관계 있을 때만 허용
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
