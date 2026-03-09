from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import SQLModel, Field, func
from pydantic import AwareDatetime


class Payment(SQLModel, table=True):
    """
    결제 내역.

    method: TOSS | KAKAO | NAVER | CASH | TRANSFER
    status: PENDING | COMPLETED | FAILED | REFUNDED
    """
    __tablename__ = "payments"

    id: Optional[UUID] = Field(
        default=None,
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    customer_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
        description="결제한 고객 ID",
    )

    membership_id: Optional[UUID] = Field(
        default=None,
        sa_type=PGUUID(as_uuid=True),
        foreign_key="memberships.id",
        nullable=True,
        description="연결된 멤버십 ID",
    )

    amount: int = Field(
        sa_type=Integer,
        nullable=False,
        description="결제 금액 (원)",
    )

    method: str = Field(
        sa_type=String(20),
        nullable=False,
        description="결제 수단 (TOSS | KAKAO | NAVER | CASH | TRANSFER)",
    )

    status: str = Field(
        default="PENDING",
        sa_type=String(20),
        nullable=False,
        description="결제 상태 (PENDING | COMPLETED | FAILED | REFUNDED)",
    )

    pg_payment_id: Optional[str] = Field(
        default=None,
        sa_type=String(200),
        nullable=True,
        description="PG사 결제 고유 ID (토스 paymentKey 등)",
    )

    created_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )
