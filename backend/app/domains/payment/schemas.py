from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    customer_id: UUID
    membership_id: Optional[UUID] = None
    amount: int                    # 원 단위
    method: str                    # TOSS | KAKAO | NAVER | CASH | TRANSFER
    pg_payment_id: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PaymentRead(BaseModel):
    id: UUID
    customer_id: UUID
    membership_id: Optional[UUID] = None
    amount: int
    method: str
    status: str
    pg_payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentStatusUpdate(BaseModel):
    status: str  # COMPLETED | FAILED | REFUNDED

    model_config = ConfigDict(extra="forbid")
