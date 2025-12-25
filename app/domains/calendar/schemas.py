from __future__ import annotations

from datetime import date, time, datetime
from typing import Optional, Literal, List
from uuid import UUID

from pydantic import BaseModel, Field


# ---------- Calendar ----------

class CalendarCreate(BaseModel):
    """
    호스트가 '자체 캘린더'를 처음 생성할 때 입력
    """
    topics: List[str] = Field(default_factory=list, description="게스트와 나눌 주제들")
    description: str = Field(..., min_length=1, description="게스트에게 보여 줄 설명")


class CalendarUpdate(BaseModel):
    """
    호스트가 캘린더 정보를 수정할 때 입력(부분 수정)
    """
    topics: Optional[List[str]] = Field(default=None, description="게스트와 나눌 주제들")
    description: Optional[str] = Field(default=None, min_length=1, description="게스트에게 보여 줄 설명")


class CalendarRead(BaseModel):
    """
    캘린더 조회 응답(호스트/게스트 공용)
    """
    id: int
    host_id: UUID
    topics: List[str]
    description: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- TimeSlot ----------

class TimeSlotCreate(BaseModel):
    """
    반복 시간대 생성(호스트 전용)
    weekdays: 0=월 ... 6=일
    """
    start_time: time
    end_time: time
    weekdays: List[int] = Field(..., min_length=1, description="예약 가능한 요일들 (0=월 ... 6=일)")

    # 간단 검증(운영에서 반드시 필요)
    # - end_time > start_time
    # - weekdays 값 범위(0~6)
    # Pydantic v2 기준 validator를 쓰면 더 엄격하게 가능하지만,
    # 여기서는 라우터에서도 방어하므로 스키마는 최소로 둠.


class TimeSlotRead(BaseModel):
    id: int
    calendar_id: int
    start_time: time
    end_time: time
    weekdays: List[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Availability ----------

class AvailabilitySlot(BaseModel):
    time_slot_id: int
    start_time: time
    end_time: time


class AvailabilityDay(BaseModel):
    date: date
    slots: List[AvailabilitySlot]


class AvailabilityResponse(BaseModel):
    host_id: UUID
    start: date
    end: date
    days: List[AvailabilityDay]


# ---------- Booking ----------

BookingStatus = Literal["CONFIRMED", "CANCELLED", "COMPLETED"]


class BookingCreate(BaseModel):
    """
    게스트가 예약 생성할 때 입력
    """
    time_slot_id: int
    when: date
    topic: str = Field(..., min_length=1)
    description: Optional[str] = Field(default=None)


class BookingRead(BaseModel):
    """
    예약 조회 응답
    """
    id: int
    when: date
    topic: str
    status: BookingStatus
    description: Optional[str]
    time_slot_id: int
    guest_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookingCancelResponse(BaseModel):
    id: int
    status: BookingStatus
    updated_at: datetime
