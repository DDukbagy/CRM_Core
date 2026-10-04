from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    # 임시 휴무일이면 true (예전 응답과 호환)
    is_holiday: bool = False
    # 휴무 종류: RECURRING(정기 휴무일) / TEMPORARY(임시 휴무일) / null(영업일)
    off_type: Literal["RECURRING", "TEMPORARY"] | None = None

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
    """특정 날짜만의 예외
    - kind=CLOSE: time_slot_ids 가 비면 임시 휴무일(하루 전체), 있으면 그 시간만 휴무
    - kind=OPEN : 정기 휴무일 중 그날만 영업. time_slot_ids 가 비면 하루 전체, 있으면 그 시간만
    """
    date: date
    time_slot_ids: list[int] = []
    kind: Literal["CLOSE", "OPEN"] = "CLOSE"
    reason: str | None = None

    model_config = {"extra": "forbid"}


class CalendarBlockRead(BaseModel):
    id: int
    calendar_id: int
    start_date: date
    end_date: date
    time_slot_id: int | None = None
    kind: str = "CLOSE"
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

