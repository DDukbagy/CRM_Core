from datetime import datetime, timezone, date
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Text, Boolean, SmallInteger, Date, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import SQLModel, Field, func
from pydantic import AwareDatetime


class Membership(SQLModel, table=True):
    """
    고객-강사 간 멤버십 (회원권).

    type:
    - TIMES  : 횟수제 (total_count / remaining_count)
    - PERIOD : 기간제 (started_at / expires_at)
    """
    __tablename__ = "memberships"

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
        description="고객 ID",
    )

    instructor_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
        description="강사 ID",
    )

    type: str = Field(
        sa_type=String(10),
        nullable=False,
        description="멤버십 타입 (TIMES | PERIOD)",
    )

    # TIMES 타입용
    total_count: Optional[int] = Field(
        default=None,
        sa_type=SmallInteger,
        nullable=True,
        description="총 레슨 횟수 (TIMES 타입)",
    )
    remaining_count: Optional[int] = Field(
        default=None,
        sa_type=SmallInteger,
        nullable=True,
        description="남은 레슨 횟수 (TIMES 타입)",
    )

    # 공통 날짜
    started_at: Optional[date] = Field(
        default=None,
        sa_type=Date,
        nullable=True,
        description="멤버십 시작일",
    )
    expires_at: Optional[date] = Field(
        default=None,
        sa_type=Date,
        nullable=True,
        description="멤버십 만료일 (PERIOD 타입)",
    )

    is_active: bool = Field(
        default=True,
        sa_type=Boolean,
        nullable=False,
        description="활성 여부",
    )

    notes: Optional[str] = Field(
        default=None,
        sa_type=Text,
        nullable=True,
        description="메모",
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
