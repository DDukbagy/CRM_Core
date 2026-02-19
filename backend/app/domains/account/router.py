from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.account.models import User
from app.domains.account.schemas import (
    UserRead,
    UsersListResponse,
    UserUpdate,
)

router = APIRouter(
    prefix="/accounts",
    tags=["Account"],
)


def _make_username(user_id: UUID, email: str | None) -> str:
    """
    자동 생성 username 규칙
    - email이 있으면 email prefix 우선
    - 없으면 user_<uuid앞8자리>
    """
    base = (email.split("@")[0] if email else f"user_{str(user_id)[:8]}")
    return base[:30]


async def _get_or_create_user_row(
    session: AsyncSession,
    user_id: UUID,
    email: str | None,
    display_name: str | None,
) -> User:
    """
    users row가 있으면 반환, 없으면 생성(자동 동기화)
    - username 충돌 대비해서 몇 번 재시도
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    username_base = _make_username(user_id, email)
    display = display_name or "사용자"

    for i in range(5):
        suffix = "" if i == 0 else "_" + secrets.token_hex(2)  # 4 hex
        username = (username_base + suffix)[:40]

        new_user = User(
            id=user_id,
            username=username,
            email=email,
            display_name=display,
            password=None,     # password는 DB에서 nullable
            role="CUSTOMER",
        )
        session.add(new_user)

        try:
            await session.commit()
            await session.refresh(new_user)
            return new_user
        except IntegrityError:
            await session.rollback()

            # 동시에 생성됐을 가능성 → 다시 조회해서 있으면 그걸 반환
            result = await session.execute(select(User).where(User.id == user_id))
            existing = result.scalar_one_or_none()
            if existing:
                return existing

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="사용자 자동 생성에 실패했습니다. (username 충돌 등)",
    )


@router.get("/me", response_model=UserRead)
async def get_my_account(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    내 계정 조회
    - 로그인한 유저 본인만 접근
    - users row가 없으면 자동 생성(동기화)
    """
    user_id = UUID(current_user["id"])
    email = current_user.get("email")
    display_name = current_user.get("display_name")

    user = await _get_or_create_user_row(session, user_id, email, display_name)
    return user


@router.patch("/me", response_model=UserRead)
async def update_my_account(
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    내 프로필 일부 수정(PATCH)
    - username/email/display_name 중 들어온 것만 업데이트
    - users row가 없으면 먼저 자동 생성(동기화) 후 업데이트
    """
    user_id = UUID(current_user["id"])
    email = current_user.get("email")
    display_name = current_user.get("display_name")

    user = await _get_or_create_user_row(session, user_id, email, display_name)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return user  # 수정할 게 없으면 그대로 반환

    # 허용된 필드만 반영
    if "username" in data and data["username"] is not None:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "display_name" in data and data["display_name"] is not None:
        user.display_name = data["display_name"]

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except IntegrityError:
        await session.rollback()
        # username/email unique 충돌 같은 케이스
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 username 또는 email 입니다.",
        )


@router.get("/{user_id}", response_model=UserRead)
async def get_account_by_id(
    user_id: UUID,
    current_host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
    session: AsyncSession = Depends(get_session),
):
    """
    특정 유저 조회(호스트 전용)
    - 현재는 host 권한만 체크
    - 운영 확장 시 current_host를 이용해 코치별 범위 제한 로직을 붙일 수 있음
    """
    _ = current_host

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


@router.get("", response_model=UsersListResponse)
async def list_accounts(
    current_host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
):
    """
    유저 목록 조회(호스트 전용)
    - UsersListResponse(items/total/limit/offset)로 고정
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
