from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarCreate(BaseModel):
    """
    호스트가 '자체 캘린더'를 처음 생성할 때 입력
    """
    topics: list[str] = Field(default_factory=list, description="게스트와 나눌 주제들")
    description: str = Field(min_length=1, description="게스트에게 보여 줄 설명")

    model_config = {"extra": "forbid"}


class CalendarUpdate(BaseModel):
    """
    호스트가 캘린더 정보를 수정할 때 입력(부분 수정)
    """
    topics: list[str] | None = Field(default=None, description="게스트와 나눌 주제들")
    description: str | None = Field(default=None, min_length=1, description="게스트에게 보여 줄 설명")

    model_config = {"extra": "forbid"}


class CalendarRead(BaseModel):
    """
    캘린더 조회 응답(호스트/게스트 공용)
    """
    id: int
    host_id: UUID
    topics: list[str]
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimeSlotCreate(BaseModel):
    """
    반복 시간대 생성(호스트 전용)
    weekdays: 0=월 ... 6=일
    """
    start_time: time
    end_time: time
    weekdays: list[int] = Field(min_length=1, description="예약 가능한 요일들 (0=월 ... 6=일)")

    model_config = {"extra": "forbid"}


class TimeSlotUpdate(BaseModel):
    """
    반복 시간대 수정(호스트 전용, 부분 수정)
    """
    start_time: time | None = None
    end_time: time | None = None
    weekdays: list[int] | None = None

    model_config = {"extra": "forbid"}


class TimeSlotRead(BaseModel):
    id: int
    calendar_id: int
    start_time: time
    end_time: time
    weekdays: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AvailabilitySlot(BaseModel):
    time_slot_id: int
    start_time: time
    end_time: time

    model_config = {"extra": "forbid"}


class AvailabilityDay(BaseModel):
    date: date
    slots: list[AvailabilitySlot]

    model_config = {"extra": "forbid"}


class AvailabilityResponse(BaseModel):
    """
    특정 기간 동안 '예약 가능한 시간표'를 계산해서 내려주는 응답
    - 실제 구현에서는 bookings(이미 예약된 것)까지 반영해서 slots를 필터링하게 됨
    """
    host_id: UUID
    start: date
    end: date
    days: list[AvailabilityDay]

    model_config = {"extra": "forbid"}


BookingStatus = Literal["CONFIRMED", "CANCELLED", "COMPLETED"]


class BookingCreate(BaseModel):
    """
    게스트가 예약 생성할 때 입력
    - description은 DB에서 nullable 허용이므로 Optional
    """
    time_slot_id: int
    when: date
    topic: str = Field(min_length=1)
    description: str | None = None

    model_config = {"extra": "forbid"}


class BookingRead(BaseModel):
    """
    예약 조회 응답
    """
    id: int
    when: date
    topic: str
    status: BookingStatus
    description: str | None
    time_slot_id: int
    guest_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingCancelResponse(BaseModel):
    """
    예약 취소 응답(최소 응답 형태)
    - 클라이언트가 상태 변경만 빠르게 확인할 수 있게 함
    """
    id: int
    status: BookingStatus
    updated_at: datetime

    model_config = {"extra": "forbid"}
