from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.membership.models import Membership
from app.domains.membership.schemas import MembershipCreate, MembershipRead, MembershipUpdate
from app.domains.users.models import User

router = APIRouter(prefix="/memberships", tags=["Membership"])


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def create_membership(
    data: MembershipCreate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    강사가 고객에게 멤버십(회원권) 생성.
    - INSTRUCTOR: 본인이 담당하는 고객만 가능
    - ADMIN: 제한 없음
    """
    instructor_id = UUID(str(instructor.id))

    # 고객 존재 확인
    customer_res = await session.execute(select(User).where(User.id == data.customer_id))
    customer = customer_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 강사 권한 확인 (내 고객만)
    if instructor.role == "INSTRUCTOR" and customer.manager_id != instructor_id:
        raise HTTPException(status_code=403, detail="본인이 담당하는 고객에게만 멤버십을 생성할 수 있습니다.")

    remaining = data.total_count if data.type == "TIMES" else None

    membership = Membership(
        customer_id=data.customer_id,
        instructor_id=instructor_id,
        type=data.type,
        total_count=data.total_count,
        remaining_count=remaining,
        started_at=data.started_at,
        expires_at=data.expires_at,
        is_active=True,
        notes=data.notes,
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership


@router.get("", response_model=list[MembershipRead])
async def list_memberships(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
    active_only: bool = True,
):
    """
    멤버십 목록 조회.
    - CUSTOMER: 본인 멤버십만
    - INSTRUCTOR: 본인 고객들의 멤버십
    - ADMIN: 전체 (customer_id 필터 지원)
    """
    user_id = UUID(str(user.id))
    stmt = select(Membership)

    if user.role == "CUSTOMER":
        stmt = stmt.where(Membership.customer_id == user_id)
    elif user.role == "INSTRUCTOR":
        stmt = stmt.where(Membership.instructor_id == user_id)
        if customer_id:
            stmt = stmt.where(Membership.customer_id == customer_id)
    else:
        # ADMIN
        if customer_id:
            stmt = stmt.where(Membership.customer_id == customer_id)

    if active_only:
        stmt = stmt.where(Membership.is_active == True)  # noqa: E712

    stmt = stmt.order_by(Membership.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{membership_id}", response_model=MembershipRead)
async def get_membership(
    membership_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    res = await session.execute(select(Membership).where(Membership.id == membership_id))
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    user_id = UUID(str(user.id))
    if user.role == "CUSTOMER" and membership.customer_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.role == "INSTRUCTOR" and membership.instructor_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return membership


@router.patch("/{membership_id}", response_model=MembershipRead)
async def update_membership(
    membership_id: UUID,
    data: MembershipUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 멤버십 상태/잔여횟수/만료일 수정."""
    res = await session.execute(select(Membership).where(Membership.id == membership_id))
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    user_id = UUID(str(user.id))
    if user.role == "INSTRUCTOR" and membership.instructor_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(membership, field, value)

    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership
