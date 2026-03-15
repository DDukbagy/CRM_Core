from datetime import datetime, time, timezone, date
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID
from enum import Enum

from pydantic import AwareDatetime
from sqlalchemy import Index, text, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from app.domains.users.models import User

# 예약 타입 정의 (일반 레슨 / 휴무)
class BookingType(str, Enum):
    LESSON = "LESSON"          # 일반 예약 (레슨, 게임 등)
    HOLIDAY = "HOLIDAY"        # 휴무 (강사 일정 차단)
    WORK_OVERRIDE = "WORK_OVERRIDE"  # 정기 휴무 요일을 특정 날짜만 영업일로 전환

class Calendar(SQLModel, table=True):
    __tablename__ = "calendars"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    topics: List[str] = Field(sa_type=JSONB, description="게스트와 나눌 주제들")
    description: str = Field(sa_type=Text, description="게스트에게 보여 줄 설명")

    host_id: UUID = Field(foreign_key="users.id", unique=True)
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

    id: Optional[int] = Field(default=None, primary_key=True)
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

    calendar_id: int = Field(foreign_key="calendars.id")
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


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "uq_booking_active_slot_date",
            "when",
            "time_slot_id",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    when: date
    topic: str
    
    # 예약 타입 (기본값: LESSON)
    type: BookingType = Field(default=BookingType.LESSON, description="LESSON / HOLIDAY")
    
    # REQUESTED
    status: str = Field(default="REQUESTED", description="REQUESTED / CONFIRMED / CANCELLED / COMPLETED")

    description: Optional[str] = Field(default=None, sa_type=Text, description="예약 설명")

    # 취소 사유
    cancel_reason: Optional[str] = Field(default=None, sa_type=Text, description="취소/거절 사유")

    membership_id: Optional[UUID] = Field(
        default=None,
        sa_type=PGUUID(as_uuid=True),
        foreign_key="memberships.id",
        nullable=True,
        description="차감할 멤버십 ID",
    )

    time_slot_id: int = Field(foreign_key="time_slots.id")
    time_slot: TimeSlot = Relationship(back_populates="bookings")

    guest_id: UUID = Field(foreign_key="users.id")
    guest: "User" = Relationship(back_populates="bookings")

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


class CalendarBlock(SQLModel, table=True):
    """
    특정 기간 동안 예약을 막는 예외일(휴무/휴가/공휴일) 블록
    - start_date ~ end_date (inclusive)
    """
    __tablename__ = "calendar_blocks"
    __table_args__ = (
        Index("ix_calendar_blocks_calendar_id", "calendar_id"),
        Index("ix_calendar_blocks_range", "calendar_id", "start_date", "end_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    calendar_id: int = Field(foreign_key="calendars.id")
    calendar: Calendar = Relationship(back_populates="blocks")

    start_date: date
    end_date: date

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