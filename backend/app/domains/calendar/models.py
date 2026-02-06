from datetime import datetime, time, timezone, date
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID
from enum import Enum

from pydantic import AwareDatetime
from sqlalchemy import Index, text, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy_utc import UtcDateTime
from sqlmodel import Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from app.domains.account.models import User

# 예약 타입 정의 (일반 레슨 / 휴무)
class BookingType(str, Enum):
    LESSON = "LESSON"     # 일반 예약 (레슨, 게임 등)
    HOLIDAY = "HOLIDAY"   # 휴무 (강사 일정 차단)

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
    
    status: str = Field(default="CONFIRMED", description="CONFIRMED / CANCELLED / COMPLETED")
    description: Optional[str] = Field(default=None, sa_type=Text, description="예약 설명")

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