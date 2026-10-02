from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import text
from sqlmodel import SQLModel, Field, func


NAMED_FEE = 5_000  # 네임드 강사 매칭 수수료(원)


class MatchRequest(SQLModel, table=True):
    __tablename__ = "instructor_match_requests"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    customer_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    instructor_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    # MATCH | CONSULTATION
    request_type: str = Field(default="MATCH", max_length=20)
    # PENDING | ACCEPTED | REJECTED | CANCELLED
    status: str = Field(default="PENDING", max_length=20)
    # 0 = 무료(NORMAL), 5000 = 유료(NAMED)
    fee: int = Field(default=0)
    note: Optional[str] = Field(default=None, sa_type=Text)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )
