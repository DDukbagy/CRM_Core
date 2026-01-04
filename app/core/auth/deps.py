from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
    is_host: bool


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
    user_id = claims.get("sub")
    email = claims.get("email")
    phone = claims.get("phone")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    result = await session.execute(
        text(
            """
            select id, email, username, display_name, is_host
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
                insert into public.users (id, username, email, display_name, is_host)
                values (:id, :username, :email, :display_name, false)
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
            is_host=False,
        )

    return CurrentUser(
        id=str(row[0]),
        email=row[1],
        phone=phone,
        username=row[2],
        display_name=row[3],
        is_host=bool(row[4]),
    )


def require_host(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_host:
        raise HTTPException(status_code=403, detail="Host role required")
    return user
