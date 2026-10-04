from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import Column, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import Field, Relationship, SQLModel, func

from app.domains.calendar.models import TimeSlot

if TYPE_CHECKING:
    from app.domains.users.models import User

# 예약 타입. 예약은 레슨(LESSON)만 받는다.
# HOLIDAY·WORK_OVERRIDE 는 예전에 휴무를 예약 행으로 저장하던 값으로, DB enum(bookingtype)과 과거 마이그레이션이
# 이 값을 참조하므로 남겨 둔다. 휴무·영업일 전환은 CalendarBlock(CLOSE/OPEN)으로 저장한다 (u6v7w8x9y0z1).
class BookingType(str, Enum):
    LESSON = "LESSON"
    HOLIDAY = "HOLIDAY"              # 사용 안 함 (과거 값)
    WORK_OVERRIDE = "WORK_OVERRIDE"  # 사용 안 함 (과거 값)

# 레슨이 그 시간을 차지하고 있는 상태 (휴무로 닫거나 열어 둔 날을 되돌릴 때 확인)
ACTIVE_LESSON_STATUSES = ("REQUESTED", "CONFIRMED", "CANCEL_REQUESTED")


def _booking_unique_index(name: str, booking_type: str) -> Index:
    """같은 날짜·슬롯에 같은 종류의 (취소 아닌) 예약은 하나만 (마이그레이션 h2i3j4k5l6m7 이 만든 인덱스)

    ddl_if(...False): init 마이그레이션의 create_all 이 이 인덱스를 먼저 만들지 않게 한다.
    만들면 h2i3j4k5l6m7 의 CREATE INDEX 가 '이미 있음'으로 실패한다.
    선언은 alembic check / autogenerate 비교용으로만 쓰인다.
    """
    return Index(
        name,
        "when",
        "time_slot_id",
        unique=True,
        postgresql_where=text(f"status <> 'CANCELLED' AND type = '{booking_type}'"),
    ).ddl_if(callable_=lambda *args, **kwargs: False)


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        _booking_unique_index("uq_booking_lesson_slot_date", "LESSON"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    when: date
    topic: Optional[str] = None
    
    # 예약 타입 (기본값: LESSON)
    type: BookingType = Field(default=BookingType.LESSON, description="LESSON / HOLIDAY")
    
    # REQUESTED
    status: str = Field(default="REQUESTED", description="REQUESTED / CONFIRMED / CANCELLED / COMPLETED")

    description: Optional[str] = Field(default=None, sa_type=Text, description="예약 설명")

    # 취소 사유
    cancel_reason: Optional[str] = Field(default=None, sa_type=Text, description="취소/거절 사유")

    time_slot_id: int = Field(sa_column=Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False))
    time_slot: TimeSlot = Relationship(back_populates="bookings")

    guest_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
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
