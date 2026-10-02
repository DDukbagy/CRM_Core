from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.core.retention import retention_cutoff
from app.domains.membership.models import Membership
from app.domains.membership.schemas import MembershipCreate, MembershipUpdate
from app.domains.users.models import User


class MembershipRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_404(self, membership_id: UUID) -> Membership:
        membership = (
            await self.session.execute(select(Membership).where(Membership.id == membership_id))
        ).scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
        return membership

    # 강사는 본인 담당 고객에게만 생성. TIMES 는 잔여 횟수 = 총 횟수로 시작
    async def create(self, data: MembershipCreate, instructor: CurrentUser) -> Membership:
        instructor_id = UUID(str(instructor.id))

        customer = (await self.session.execute(select(User).where(User.id == data.customer_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        if instructor.role == "INSTRUCTOR" and customer.manager_id != instructor_id:
            raise HTTPException(status_code=403, detail="본인이 담당하는 고객에게만 멤버십을 생성할 수 있습니다.")

        membership = Membership(
            customer_id=data.customer_id,
            instructor_id=instructor_id,
            type=data.type,
            total_count=data.total_count,
            remaining_count=data.total_count if data.type == "TIMES" else None,
            started_at=data.started_at,
            expires_at=data.expires_at,
            is_active=True,
            notes=data.notes,
        )
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    # 역할별 목록: 고객은 본인, 강사는 본인이 만든 멤버십, 그 외(관리자)는 전체
    async def list_for_user(
        self, user: CurrentUser, customer_id: Optional[UUID] = None, active_only: bool = True
    ) -> list[Membership]:
        user_id = UUID(str(user.id))
        stmt = select(Membership)

        if user.role == "CUSTOMER":
            stmt = stmt.where(Membership.customer_id == user_id)
        else:
            if user.role == "INSTRUCTOR":
                stmt = stmt.where(Membership.instructor_id == user_id)
            if customer_id:
                stmt = stmt.where(Membership.customer_id == customer_id)

        if active_only:
            stmt = stmt.where(Membership.is_active == True)  # noqa: E712

        stmt = stmt.order_by(Membership.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    def ensure_can_view(self, membership: Membership, user: CurrentUser) -> None:
        user_id = UUID(str(user.id))
        if user.role == "CUSTOMER" and membership.customer_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if user.role == "INSTRUCTOR" and membership.instructor_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    # 강사가 상태/잔여횟수/만료일 수정 (본인이 만든 멤버십만)
    async def update(self, membership: Membership, data: MembershipUpdate, user: CurrentUser) -> Membership:
        if user.role == "INSTRUCTOR" and membership.instructor_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(membership, field, value)

        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    # ── 예약(calendar)에서 쓰는 규칙 ─────────────────────────────────────────

    async def validate_for_booking(self, membership_id: UUID, customer_id: UUID) -> Membership:
        """레슨 예약에 연결할 멤버십 확인: 본인 소유, 활성, 잔여 횟수, 만료일"""
        membership = await self.get_or_404(membership_id)
        if membership.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Membership does not belong to you")
        if not membership.is_active:
            raise HTTPException(status_code=400, detail="수강권이 비활성 상태입니다.")
        if membership.type == "TIMES" and (membership.remaining_count or 0) <= 0:
            raise HTTPException(status_code=400, detail="잔여 횟수가 없습니다.")
        if membership.type == "PERIOD" and membership.expires_at and membership.expires_at < date.today():
            raise HTTPException(status_code=400, detail="수강권이 만료되었습니다.")
        return membership

    async def deduct_for_lesson(self, membership_id: UUID) -> None:
        """레슨 완료 시 TIMES 멤버십 1회 차감, 0이 되면 비활성 (commit 은 호출한 쪽에서)"""
        membership = (
            await self.session.execute(select(Membership).where(Membership.id == membership_id))
        ).scalar_one_or_none()
        if membership and membership.type == "TIMES" and membership.remaining_count is not None:
            membership.remaining_count = max(0, membership.remaining_count - 1)
            if membership.remaining_count == 0:
                membership.is_active = False
            self.session.add(membership)

    # ── 계약 기록 보존 (회원 삭제 시) ─────────────────────────────────────────
    # 고객·강사 어느 쪽이 지워져도 계약 기록은 남아야 한다. 기준은 마지막 변경(사용·만료 처리) 시점

    @staticmethod
    def _of_user(user_id: UUID):
        return or_(Membership.customer_id == user_id, Membership.instructor_id == user_id)

    async def count_retained_for_user(self, user_id: UUID) -> int:
        """보존 기간이 끝나지 않은 멤버십 수"""
        return (
            await self.session.execute(
                select(func.count()).select_from(Membership).where(self._of_user(user_id), Membership.updated_at > retention_cutoff())
            )
        ).scalar_one()

    async def delete_expired_for_user(self, user_id: UUID) -> None:
        """보존 기간이 끝난 멤버십 삭제 (commit 은 호출한 쪽에서)"""
        await self.session.execute(
            delete(Membership).where(self._of_user(user_id), Membership.updated_at <= retention_cutoff())
        )
