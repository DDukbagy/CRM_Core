from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Integer, text
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
    # customer_pass_id 의 FK(→ customer_passes)는 마이그레이션 w8x9y0z1a2b3 이 만든다.
    # init 마이그레이션(create_all)에는 customer_passes 가 없어 여기서 선언하면 실패하므로,
    # 비교 명령(alembic check)일 때만 alembic/env.py 가 이 FK 를 붙인다 (passes 모델을 올리는 것과 같은 이유)

    id: Optional[UUID] = Field(
        default=None,
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    # RESTRICT: 결제 기록은 보존 기간(PAYMENT_RETENTION_YEARS) 동안 회원 삭제로 함께 지워지면 안 된다
    customer_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        description="결제한 고객 ID",
    )

    # 이 결제로 산 수강권 (멤버십은 수강권으로 통합, 2026-10-04)
    customer_pass_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="연결된 발급 수강권 ID",
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
