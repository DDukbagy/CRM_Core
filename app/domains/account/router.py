from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.dependencies import get_current_host, get_current_user
from app.db import get_session
from app.domains.account.models import User
from app.domains.account.schemas import UserRead, UsersListResponse

router = APIRouter(
    prefix="/accounts",
    tags=["Account"],
)


@router.get("/me", response_model=UserRead)
async def get_my_account(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    내 계정 조회
    - 로그인한 유저 본인만 접근
    - response_model=UserRead로 민감정보(password 등) 노출 방지
    """
    user_id = UUID(current_user["id"])

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 정보가 DB에 없습니다. (users row가 아직 없을 수 있습니다.)",
        )

    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_account_by_id(
    user_id: UUID,
    current_host: dict = Depends(get_current_host),
    session: AsyncSession = Depends(get_session),
):
    """
    특정 유저 조회(호스트 전용)
    - 현재는 host 권한만 체크
    - 운영 확장 시 current_host를 이용해 '코치별 소유권/범위 제한' 로직을 붙일 수 있음
    """
    # (현재는 권한 체크만 하고 값은 쓰지 않음. 운영 확장 시 사용 예정)
    _ = current_host

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


@router.get("", response_model=UsersListResponse)
async def list_accounts(
    current_host: dict = Depends(get_current_host),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
):
    """
    유저 목록 조회(호스트 전용)
    - limit/offset 기반 페이지네이션 기본 틀
    - response_model을 UsersListResponse로 고정하여 메타데이터 확장에 안전
    """
    _ = current_host

    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    users = result.scalars().all()

    total_stmt = select(func.count()).select_from(User)
    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    return {
        "items": users,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
