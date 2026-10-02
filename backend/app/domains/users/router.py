from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.users.repository import UserRepository, safe_uuid
from app.domains.users.schemas import (
    UserRead,
    UsersListResponse,
    UserUpdate,
    UserCreate,
    PushTokenUpdate,
    RegisterCustomerByEmail,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_my_account(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 계정 조회 (users 행이 없으면 자동 생성)"""
    return await UserRepository(session).get_or_create_me(current_user)


@router.patch("/me", response_model=UserRead)
async def update_my_account(
    payload: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 프로필 부분 수정 (역할·상태·담당 강사는 바꿀 수 없음)"""
    return await UserRepository(session).update_me(current_user, payload)


@router.get("", response_model=UsersListResponse)
async def list_users(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    role: str | None = None,
):
    """유저 목록 (관리자: 전체 / 강사: 담당 고객 / 그 외: 본인). role 로 필터"""
    users, total, limit, offset = await UserRepository(session).list_for_user(current_user, limit, offset, role)
    return {"items": users, "total": total, "limit": limit, "offset": offset}


@router.post("/me/customers", response_model=UserRead, status_code=200)
async def register_customer_by_email(
    body: RegisterCustomerByEmail,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_role({"INSTRUCTOR"})),
):
    """강사가 이메일로 고객을 담당 고객으로 등록."""
    return await UserRepository(session).register_customer_by_email(safe_uuid(current_user.id), body.email)


@router.put("/me/push-token", status_code=204)
async def update_push_token(
    body: PushTokenUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """Expo Push Token 저장 (로그인 후 앱에서 호출)"""
    await UserRepository(session).set_push_token(user.id, body.token)


@router.delete("/me/push-token", status_code=204)
async def delete_push_token(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """로그아웃 시 Push Token 제거"""
    await UserRepository(session).set_push_token(user.id, None)


@router.post("/me/withdraw", response_model=UserRead)
async def withdraw_my_account(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """회원 탈퇴 (로그인 차단 + 개인정보 익명화, 결제 기록은 법정 기간 보존)"""
    return await UserRepository(session).withdraw(safe_uuid(current_user.id), current_user)


@router.post("/{user_id}/withdraw", response_model=UserRead)
async def withdraw_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_role({"ADMIN", "INSTRUCTOR"})),
):
    """관리자·담당 강사가 회원을 탈퇴 처리 (삭제할 수 없는 회원에게 사용)"""
    return await UserRepository(session).withdraw(user_id, current_user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_detail(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """유저 상세 (관리자: 전체 / 강사: 본인·담당 고객 / 고객: 본인·담당 강사)"""
    return await UserRepository(session).get_visible(user_id, current_user)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_role({"ADMIN", "INSTRUCTOR"})),
):
    """[신규 회원 등록] 관리자·강사. 강사는 일반 고객만, 담당 강사는 본인으로 지정"""
    return await UserRepository(session).create(user_in, current_user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """특정 회원 정보 수정 (아이디·이메일·이름)"""
    return await UserRepository(session).update(user_id, user_in, current_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """특정 회원 삭제 (관리자: 전체 / 강사: 담당 고객)"""
    await UserRepository(session).delete(user_id, current_user)
    return None
