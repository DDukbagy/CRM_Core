from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.booking.models import BookingType


BookingStatus = Literal["REQUESTED", "CONFIRMED", "CANCEL_REQUESTED", "CANCELLED", "COMPLETED", "NO_SHOW"]


class BookingCreate(BaseModel):
    """
    게스트가 예약 생성할 때 입력
    """
    time_slot_id: int
    when: date
    topic: str | None = None
    description: str | None = None

    # 예약은 레슨만 (휴무·영업일 전환은 /calendars/me/blocks)
    type: BookingType = BookingType.LESSON

    model_config = {"extra": "forbid"}


class BookingRead(BaseModel):
    """
    예약 조회 응답
    """
    id: int
    when: date
    topic: str | None = None
    status: BookingStatus
    type: BookingType  # 타입 정보 포함
    description: str | None
    cancel_reason: str | None = None
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


class BookingConfirmRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=200, description="수업 내용 (강사가 확정 시 지정)")

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
