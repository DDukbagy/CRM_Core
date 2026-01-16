from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.core.auth.supabase_jwt import (
    SupabaseJWTError,
    SupabaseJWTExpired,
    verify_supabase_access_token,
)

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


async def _get_or_create_user_from_claims(
    claims: dict,
    session: AsyncSession,
) -> CurrentUser:
    """
    claims -> CurrentUser (JIT 포함)
    get_current_user / get_current_user_optional이 동일 로직을 공유한다.
    """
    user_id = claims.get("sub")
    email = claims.get("email")
    phone = claims.get("phone")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    result = await session.execute(
        text(
            """
            select id, email, username, display_name, role
            from public.users
            where id = :id
            """
        ),
        {"id": user_id},
    )
    row = result.first()

    if row is None:
        base = user_id.replace("-", "")[:8]
        username = f"user-{base}"
        display_name = email or phone or username

        await session.execute(
            text(
                """
                insert into public.users (id, username, email, display_name, role)
                values (:id, :username, :email, :display_name, 'CUSTOMER')
                """
            ),
            {"id": user_id, "username": username, "email": email, "display_name": display_name},
        )
        await session.commit()

        return CurrentUser(
            id=user_id,
            email=email,
            phone=phone,
            username=username,
            display_name=display_name,
            role="CUSTOMER",
        )

    return CurrentUser(
        id=str(row[0]),
        email=row[1],
        phone=phone,
        username=row[2],
        display_name=row[3],
        role=str(row[4]) if row[4] is not None else "CUSTOMER",
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
