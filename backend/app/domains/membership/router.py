from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.membership.repository import MembershipRepository
from app.domains.membership.schemas import MembershipCreate, MembershipRead, MembershipUpdate

router = APIRouter(prefix="/memberships", tags=["Membership"])


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def create_membership(
    data: MembershipCreate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 고객에게 멤버십(회원권) 생성. 강사는 본인 담당 고객만"""
    return await MembershipRepository(session).create(data, instructor)


@router.get("", response_model=list[MembershipRead])
async def list_memberships(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
    active_only: bool = True,
):
    """멤버십 목록. 고객: 본인 / 강사: 본인이 만든 멤버십 / 관리자: 전체 (customer_id 필터)"""
    return await MembershipRepository(session).list_for_user(user, customer_id, active_only)


@router.get("/{membership_id}", response_model=MembershipRead)
async def get_membership(
    membership_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MembershipRepository(session)
    membership = await repo.get_or_404(membership_id)
    repo.ensure_can_view(membership, user)
    return membership


@router.patch("/{membership_id}", response_model=MembershipRead)
async def update_membership(
    membership_id: UUID,
    data: MembershipUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 멤버십 상태/잔여횟수/만료일 수정."""
    repo = MembershipRepository(session)
    membership = await repo.get_or_404(membership_id)
    return await repo.update(membership, data, user)
