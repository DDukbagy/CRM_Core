from datetime import datetime, time, timezone, date
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID
from enum import Enum

from pydantic import AwareDatetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, ForeignKey, Identity, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from app.domains.booking.models import Booking
    from app.domains.users.models import User

class Calendar(SQLModel, table=True):
    __tablename__ = "calendars"

    # 원격 DB 와 같은 BIGINT 자동 증가(IDENTITY)
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    
    topics: List[str] = Field(sa_type=JSONB, description="게스트와 나눌 주제들")
    description: str = Field(sa_type=Text, description="게스트에게 보여 줄 설명")

    host_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True))
    host: "User" = Relationship(
        back_populates="calendar",
        sa_relationship_kwargs={"uselist": False, "single_parent": True},
    )

    time_slots: List["TimeSlot"] = Relationship(back_populates="calendar")
    blocks: List["CalendarBlock"] = Relationship(back_populates="calendar")

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


class TimeSlot(SQLModel, table=True):
    __tablename__ = "time_slots"

    # 원격 DB 와 같은 BIGINT 자동 증가(IDENTITY)
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, Identity(), primary_key=True))
    start_time: time
    end_time: time

    weekdays: List[int] = Field(sa_type=JSONB, description="예약 가능한 요일들(월0~일6)")

    # 전체 슬롯 ON/OFF
    is_active: bool = Field(
        default=True,
        nullable=False,
        sa_type=Boolean,
        description="활성 여부",
        sa_column_kwargs={"server_default": text("true")},
    )

    calendar_id: int = Field(sa_column=Column(BigInteger, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False))
    calendar: Calendar = Relationship(back_populates="time_slots")

    bookings: List["Booking"] = Relationship(back_populates="time_slot")

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


class BlockKind(str, Enum):
    CLOSE = "CLOSE"  # 닫기: 하루 전체 = 임시 휴무일, 시간 지정 = 그 시간만 휴무
    OPEN = "OPEN"    # 열기: 정기 휴무일 중 그 날짜만 영업 (하루 전체 또는 지정 시간)


class CalendarBlock(SQLModel, table=True):
    """
    특정 날짜(기간)에만 적용되는 예외 — 매주 반복 설정(슬롯·정기 휴무 요일)은 건드리지 않는다
    - start_date ~ end_date (inclusive)
    - kind: CLOSE(닫기) / OPEN(정기 휴무일 열기)
    - time_slot_id 가 있으면 그 시간만, 없으면 그 날짜 전체
    """
    __tablename__ = "calendar_blocks"
    __table_args__ = (
        Index("ix_calendar_blocks_calendar_id", "calendar_id"),
        Index("ix_calendar_blocks_range", "calendar_id", "start_date", "end_date"),
        CheckConstraint("kind IN ('CLOSE', 'OPEN')", name="ck_calendar_blocks_kind"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    calendar_id: int = Field(sa_column=Column(Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False))
    calendar: Calendar = Relationship(back_populates="blocks")

    start_date: date
    end_date: date

    time_slot_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=True),
        description="막을 시간(슬롯). 없으면 하루 전체",
    )

    kind: str = Field(
        default=BlockKind.CLOSE.value,
        sa_column=Column(String(10), nullable=False, server_default=text("'CLOSE'")),
        description="CLOSE(닫기) / OPEN(정기 휴무일 열기)",
    )

    reason: Optional[str] = Field(default=None, sa_type=Text, description="블록 사유")

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