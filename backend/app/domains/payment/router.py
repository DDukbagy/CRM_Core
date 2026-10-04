# `from __future__ import annotations`를 쓰지 않는다. @limiter.limit 래퍼 때문에 FastAPI가
# 문자열 타입(PaymentCreate)을 풀지 못해 요청 본문을 쿼리 파라미터로 해석한다(결제 등록 422).
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.payment.repository import PaymentRepository
from app.domains.payment.schemas import PaymentCreate, PaymentRead, PaymentStatusUpdate

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/payments", tags=["Payment"])


@router.post("", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_payment(
    request: Request,
    data: PaymentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """결제 내역 기록 (강사/관리자). 강사는 본인 담당 고객의 결제만 등록할 수 있다."""
    return await PaymentRepository(session).create(data, user)


@router.get("", response_model=list[PaymentRead])
async def list_payments(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
):
    """결제 내역 조회. 고객: 본인 / 강사: 담당 고객 / 관리자: 전체"""
    return await PaymentRepository(session).list_for_user(user, customer_id)


@router.patch("/{payment_id}/status", response_model=PaymentRead)
async def update_payment_status(
    payment_id: UUID,
    data: PaymentStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """관리자 전용: 결제 상태 변경 (PG 웹훅 연동 전 수동 처리용)."""
    return await PaymentRepository(session).update_status(payment_id, data.status)
