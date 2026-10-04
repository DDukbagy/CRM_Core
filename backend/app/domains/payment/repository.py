from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.core.retention import RECORD_RETENTION_YEARS, retention_cutoff
from app.domains.passes.repository import PassRepository
from app.domains.payment.models import Payment
from app.domains.payment.schemas import PaymentCreate
from app.domains.users.models import User

VALID_METHODS = {"TOSS", "KAKAO", "NAVER", "CASH", "TRANSFER"}
VALID_STATUSES = {"COMPLETED", "FAILED", "REFUNDED"}

# 결제 기록 보존 기간 (app/core/retention.py)
PAYMENT_RETENTION_YEARS = RECORD_RETENTION_YEARS


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 결제 기록: 강사는 본인 담당 고객 + 본인이 만든 멤버십에만 연결 가능. 수동 입력은 즉시 COMPLETED
    async def create(self, data: PaymentCreate, user: CurrentUser) -> Payment:
        if data.method not in VALID_METHODS:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 결제 수단입니다. 허용: {sorted(VALID_METHODS)}")

        if data.amount <= 0:
            raise HTTPException(status_code=400, detail="결제 금액은 0원보다 커야 합니다.")

        user_id = UUID(str(user.id))

        customer = (await self.session.execute(select(User).where(User.id == data.customer_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        if user.role == "INSTRUCTOR" and customer.manager_id != user_id:
            raise HTTPException(status_code=403, detail="본인이 담당하는 고객의 결제만 등록할 수 있습니다.")

        if data.customer_pass_id is not None:
            await PassRepository(self.session).ensure_linkable_to_payment(
                data.customer_pass_id, data.customer_id, user_id if user.role == "INSTRUCTOR" else None
            )

        payment = Payment(
            customer_id=data.customer_id,
            customer_pass_id=data.customer_pass_id,
            amount=data.amount,
            method=data.method,
            status="COMPLETED",
            pg_payment_id=data.pg_payment_id,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    # 역할별 목록: 고객은 본인 결제, 강사는 담당 고객(manager_id) 결제, 관리자는 전체
    async def list_for_user(self, user: CurrentUser, customer_id: Optional[UUID] = None) -> list[Payment]:
        user_id = UUID(str(user.id))
        stmt = select(Payment)

        if user.role == "CUSTOMER":
            stmt = stmt.where(Payment.customer_id == user_id)
        else:
            if user.role == "INSTRUCTOR":
                stmt = stmt.where(Payment.customer_id.in_(select(User.id).where(User.manager_id == user_id)))
            if customer_id:
                stmt = stmt.where(Payment.customer_id == customer_id)

        stmt = stmt.order_by(Payment.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_instructor(self, instructor_id: UUID) -> list[Payment]:
        """담당 고객들의 결제 (강사 매출 대시보드용)"""
        res = await self.session.execute(
            select(Payment).where(Payment.customer_id.in_(select(User.id).where(User.manager_id == instructor_id)))
        )
        return list(res.scalars().all())

    # ── 보존 기간 (회원 삭제 시 users 도메인이 호출) ─────────────────────────

    async def count_retained_for_customer(self, customer_id: UUID) -> int:
        """보존 기간이 아직 끝나지 않은 결제 수"""
        return (
            await self.session.execute(
                select(func.count()).select_from(Payment).where(
                    Payment.customer_id == customer_id, Payment.created_at > retention_cutoff()
                )
            )
        ).scalar_one()

    async def delete_expired_for_customer(self, customer_id: UUID) -> None:
        """보존 기간이 끝난 결제 기록 삭제 (commit 은 호출한 쪽에서)"""
        await self.session.execute(
            delete(Payment).where(Payment.customer_id == customer_id, Payment.created_at <= retention_cutoff())
        )

    # 관리자 수동 상태 변경 (PG 웹훅 연동 전)
    async def update_status(self, payment_id: UUID, status: str) -> Payment:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {VALID_STATUSES}")

        payment = (await self.session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        payment.status = status
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment
