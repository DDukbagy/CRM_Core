from __future__ import annotations

from uuid import UUID
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.dependencies import get_current_host, get_current_user
from app.db import get_session
from app.domains.account.models import User
from app.domains.account.schemas import UserRead, UsersListResponse

router = APIRouter(prefix="/accounts", tags=["Account"])


def _make_username(user_id: UUID, email: str | None) -> str:
    # email이 있으면 prefix 우선, 없으면 uuid 기반
    base = (email.split("@")[0] if email else f"user_{str(user_id)[:8]}")
    base = base[:30]  # 너무 길면 잘라서 suffix 붙일 여지 확보
    return base


@router.get("/me", response_model=UserRead)
async def get_my_account(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = UUID(current_user["id"])
    email = current_user.get("email")

    # 1) 먼저 조회
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    # 2) 없으면 생성(자동 동기화)
    username_base = _make_username(user_id, email)
    display_name = current_user.get("display_name") or "사용자"

    # username unique 충돌 대비(아주 드물지만 운영에서 한 번이라도 터지면 귀찮음)
    for i in range(5):
        suffix = "" if i == 0 else "_" + secrets.token_hex(2)  # 4 hex
        username = (username_base + suffix)[:40]

        new_user = User(
            id=user_id,
            username=username,
            email=email,
            display_name=display_name,
            password=None,      # ✅ nullable로 변경했으니 OK
            is_host=False,
        )

        session.add(new_user)
        try:
            await session.commit()
            await session.refresh(new_user)
            return new_user
        except IntegrityError:
            await session.rollback()
            # id conflict(동시에 두 요청이 들어온 등)면 다시 조회해서 반환
            result = await session.execute(select(User).where(User.id == user_id))
            existing = result.scalar_one_or_none()
            if existing:
                return existing
            # 아니면 username 충돌 가능성 → retry

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="사용자 자동 생성에 실패했습니다. (username 충돌 등)",
    )
