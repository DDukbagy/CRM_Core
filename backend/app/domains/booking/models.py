# 예약 모델: 레슨 예약(1건 = 레슨 1회)과 그 예약이 차지하는 시간
from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import Field, Relationship, SQLModel, func

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


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        # 아래 둘은 마이그레이션 a2b3c4d5e6f8 이 만든다. init 마이그레이션의 create_all 이 먼저 만들지 않게 ddl_if(False)
        # (선언은 alembic check 비교용)
        Index("ix_bookings_customer_pass_id", "customer_pass_id").ddl_if(callable_=lambda *args, **kwargs: False),
        # 진행 중인 레슨 예약은 반드시 수강권이 고정돼 있다. 끝난 예약(완료·노쇼·취소)은 예전 기록이라 비어 있을 수 있다
        CheckConstraint(
            "type <> 'LESSON' OR status NOT IN ('REQUESTED', 'CONFIRMED', 'CANCEL_REQUESTED') OR customer_pass_id IS NOT NULL",
            name="ck_bookings_active_lesson_has_pass",
        ).ddl_if(callable_=lambda *args, **kwargs: False),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    when: date
    topic: Optional[str] = None
    
    type: BookingType = Field(default=BookingType.LESSON, description="LESSON / HOLIDAY")
    
    status: str = Field(default="REQUESTED", description="REQUESTED / CONFIRMED / CANCELLED / COMPLETED")

    description: Optional[str] = Field(default=None, sa_type=Text, description="예약 설명")

    # 취소 사유
    cancel_reason: Optional[str] = Field(default=None, sa_type=Text, description="취소/거절 사유")

    # 이 예약이 속한 강사 캘린더. 예약이 차지하는 시간은 BookingSlot 에 있다 (레슨 1회 = 슬롯 1개 이상)
    calendar_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False, index=True)
    )

    guest_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    guest: "User" = Relationship(back_populates="bookings")

    # 이 예약으로 쓸 수강권 (예약할 때 고정, 완료·노쇼 때 여기서 차감).
    # FK(→ customer_passes, ON DELETE SET NULL)는 마이그레이션 a2b3c4d5e6f8 이 만든다. init 마이그레이션(create_all)에는
    # customer_passes 가 없어 여기서 선언하면 실패하므로, 비교 명령(alembic check)일 때만 alembic/env.py 가 붙인다 (payments 와 같은 방식).
    # SET NULL: 보존 기간이 지나 수강권 기록이 지워져도 끝난 예약은 남는다 (진행 중 예약이면 CHECK 제약이 막는다)
    customer_pass_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

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


class BookingSlot(SQLModel, table=True):
    """예약이 차지하는 시간 한 칸. 2시간 레슨이면 예약 1건에 행 2개

    holds_slot: 이 예약이 그 시간을 차지하고 있는지. 예약이 취소되면 같은 트랜잭션에서 false 로 바꿔 시간을 다시 연다
    (BookingRepository._transition). 유니크 인덱스가 "같은 날짜·슬롯을 차지하는 예약은 하나"를 지킨다.
    예약 상태는 bookings 에 있어 인덱스 조건으로 쓸 수 없으므로 이 칸을 둔다. 취소된 예약의 시간 기록은 남는다.
    """
    __tablename__ = "booking_slots"
    __table_args__ = (
        Index(
            "uq_booking_slots_slot_date",
            "when",
            "time_slot_id",
            unique=True,
            postgresql_where=text("holds_slot"),
        ),
        Index("ix_booking_slots_booking_id", "booking_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    booking_id: int = Field(sa_column=Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False))
    time_slot_id: int = Field(sa_column=Column(BigInteger, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False))
    # 예약 날짜 (bookings.when 과 같다. 유니크 인덱스에 필요해서 함께 둔다. 예약 날짜는 만든 뒤 바뀌지 않는다)
    when: date
    holds_slot: bool = Field(
        default=True, nullable=False, sa_type=Boolean, sa_column_kwargs={"server_default": text("true")}
    )
