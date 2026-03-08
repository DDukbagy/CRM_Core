from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.payment.models import Payment
from app.domains.payment.schemas import PaymentCreate, PaymentRead, PaymentStatusUpdate
from app.domains.membership.models import Membership
from app.domains.users.models import User

router = APIRouter(prefix="/payments", tags=["Payment"])

_VALID_METHODS = {"TOSS", "KAKAO", "NAVER", "CASH", "TRANSFER"}
_VALID_STATUSES = {"COMPLETED", "FAILED", "REFUNDED"}


@router.post("", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    결제 내역 기록.
    - 강사/관리자만 가능 (수동 기록 또는 PG 웹훅 연동 시 확장)
    - 강사는 반드시 본인 담당 고객의 결제만 등록 가능
    - 고객 존재 확인 + 멤버십 소유권 검증
    """
    if data.method not in _VALID_METHODS:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 결제 수단입니다. 허용: {sorted(_VALID_METHODS)}")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="결제 금액은 0원보다 커야 합니다.")

    user_id = UUID(str(user.id))

    # 고객 확인
    customer_res = await session.execute(select(User).where(User.id == data.customer_id))
    customer = customer_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # ✅ 보안: 강사는 본인 담당 고객(manager_id)만 결제 기록 가능
    if user.role == "INSTRUCTOR":
        if customer.manager_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="본인이 담당하는 고객의 결제만 등록할 수 있습니다.",
            )

    # 멤버십 확인 (연결된 경우)
    if data.membership_id:
        mem_res = await session.execute(select(Membership).where(Membership.id == data.membership_id))
        membership = mem_res.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
        # ✅ 보안: 멤버십이 해당 고객 소유인지 확인
        if membership.customer_id != data.customer_id:
            raise HTTPException(status_code=400, detail="멤버십과 고객 정보가 일치하지 않습니다.")
        # ✅ 보안: 강사는 본인이 생성한 멤버십만 결제에 연결 가능
        if user.role == "INSTRUCTOR" and membership.instructor_id != user_id:
            raise HTTPException(status_code=403, detail="본인이 생성한 멤버십만 결제에 연결할 수 있습니다.")

    payment = Payment(
        customer_id=data.customer_id,
        membership_id=data.membership_id,
        amount=data.amount,
        method=data.method,
        status="COMPLETED",  # 수동 입력은 즉시 완료 처리
        pg_payment_id=data.pg_payment_id,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


@router.get("", response_model=list[PaymentRead])
async def list_payments(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
):
    """
    결제 내역 조회.
    - CUSTOMER: 본인 결제 내역만
    - INSTRUCTOR: 본인 고객 결제 내역 (membership.instructor_id 기준)
    - ADMIN: 전체
    """
    user_id = UUID(str(user.id))
    stmt = select(Payment)

    if user.role == "CUSTOMER":
        # 고객: 본인 결제만
        stmt = stmt.where(Payment.customer_id == user_id)
    elif user.role == "INSTRUCTOR":
        # ✅ 보안: 본인 담당 고객(manager_id == instructor)의 결제만 조회
        stmt = stmt.where(
            Payment.customer_id.in_(
                select(User.id).where(User.manager_id == user_id)
            )
        )
        if customer_id:
            stmt = stmt.where(Payment.customer_id == customer_id)
    else:
        # ADMIN: 전체
        if customer_id:
            stmt = stmt.where(Payment.customer_id == customer_id)

    stmt = stmt.order_by(Payment.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


@router.patch("/{payment_id}/status", response_model=PaymentRead)
async def update_payment_status(
    payment_id: UUID,
    data: PaymentStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """
    관리자 전용: 결제 상태 변경 (PG 웹훅 연동 전 수동 처리용).
    """
    if data.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {_VALID_STATUSES}")

    res = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.status = data.status
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment
