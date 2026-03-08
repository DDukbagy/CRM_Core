from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from app.domains.calendar.models import BookingType


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
    is_active: bool = Field(default=True, description="활성 여부 (전체 ON/OFF)")

    model_config = {"extra": "forbid"}


class TimeSlotUpdate(BaseModel):
    """
    반복 시간대 수정(호스트 전용, 부분 수정)
    """
    start_time: time | None = None
    end_time: time | None = None
    weekdays: list[int] | None = None
    is_active: bool | None = Field(default=None, description="타임슬롯 활성 여부")

    model_config = {"extra": "forbid"}


class TimeSlotRead(BaseModel):
    id: int
    calendar_id: int
    start_time: time
    end_time: time
    weekdays: list[int]
    is_active: bool
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
    """
    host_id: UUID
    start: date
    end: date
    days: list[AvailabilityDay]

    model_config = {"extra": "forbid"}


BookingStatus = Literal["REQUESTED", "CONFIRMED", "CANCELLED", "COMPLETED", "NO_SHOW"]


class BookingCreate(BaseModel):
    """
    게스트가 예약 생성할 때 입력
    """
    time_slot_id: int
    when: date
    topic: str = Field(min_length=1)
    description: str | None = None
    membership_id: Optional[UUID] = None  # 차감할 멤버십 (선택)

    # 예약 타입 (기본값 LESSON, 휴무 등록 시 HOLIDAY)
    type: BookingType = BookingType.LESSON

    model_config = {"extra": "forbid"}


class BookingRead(BaseModel):
    """
    예약 조회 응답
    """
    id: int
    when: date
    topic: str
    status: BookingStatus
    type: BookingType  # 타입 정보 포함
    description: str | None
    cancel_reason: str | None = None
    membership_id: Optional[UUID] = None
    time_slot_id: int
    guest_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingUpdateRequest(BaseModel):
    """
    게스트가 REQUESTED 예약의 주제/메모를 수정할 때 입력
    """
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    model_config = {"extra": "forbid"}


class BookingCancelRequest(BaseModel):
    """
    취소/거절 시 입력(사유는 optional)
    """
    reason: str | None = Field(default=None, max_length=300, description="취소 사유(선택)")

    model_config = {"extra": "forbid"}


class BookingCancelResponse(BaseModel):
    """
    예약 취소/철회 응답(최소 응답 형태)
    """
    id: int
    status: str  # 서버 실제 값 그대로 반환
    cancel_reason: str | None = None
    updated_at: datetime

    model_config = {"extra": "forbid"}


class TimeSlotWeekdaysPatch(BaseModel):
    weekdays: list[int]

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: list[int]):
        if not v:
            raise ValueError("weekdays must not be empty")
        if any((d < 0 or d > 6) for d in v):
            raise ValueError("weekdays must be 0..6 (Mon=0..Sun=6)")
        # 중복 제거, 정렬
        return sorted(set(v))


class CalendarBlockCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=300)

    @field_validator("end_date")
    @classmethod
    def validate_range(cls, v: date, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be >= start_date")
        return v

    model_config = {"extra": "forbid"}


class CalendarBlockRead(BaseModel):
    id: int
    calendar_id: int
    start_date: date
    end_date: date
    reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}