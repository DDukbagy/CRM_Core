# 예약 요청·응답 스키마
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.booking.models import BookingType


BookingStatus = Literal["REQUESTED", "CONFIRMED", "CANCEL_REQUESTED", "CANCELLED", "COMPLETED", "NO_SHOW"]


class BookingCreate(BaseModel):
    """
    게스트가 예약 생성할 때 입력. 예약 1건 = 레슨 1회
    """
    # 이 레슨이 차지할 시간. 수강권의 회당 시간(duration_hours)만큼, 서로 이어진 슬롯이어야 한다
    time_slot_ids: list[int] = Field(min_length=1, max_length=12)
    when: date
    topic: str | None = None
    description: str | None = None

    # 예약은 레슨만 (휴무·영업일 전환은 /calendars/me/blocks)
    type: BookingType = BookingType.LESSON

    # 이 예약에 쓸 수강권. 안 보내면 서버가 그 강사의 가장 오래된 쓸 수 있는 수강권을 고른다
    customer_pass_id: int | None = None

    model_config = {"extra": "forbid"}


class BookingRead(BaseModel):
    """
    예약 조회 응답
    """
    id: int
    when: date
    topic: str | None = None
    status: BookingStatus
    type: BookingType
    description: str | None
    cancel_reason: str | None = None
    time_slot_ids: list[int]         # 이 레슨이 차지하는 슬롯 (시작 시각 순)
    start_time: time | None = None   # 첫 슬롯의 시작 ~ 마지막 슬롯의 끝
    end_time: time | None = None
    guest_id: UUID
    customer_pass_id: int | None = None  # 예약에 고정된 수강권 (이 기능 이전에 끝난 예약은 비어 있음)
    created_at: datetime
    updated_at: datetime


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


class AdminBookingRead(BookingRead):
    """관리자 화면용 예약: 누구의 레슨인지 이름을 붙인다"""
    instructor_id: UUID | None = None
    instructor_name: str | None = None
    guest_name: str | None = None


class BookingCleanupResponse(BaseModel):
    """지난 예약 자동 정리 한 번의 결과 (건수)"""
    completed: int                 # 수업 후 3일이 지나 완료·차감한 확정 예약
    cancelled: int                 # 수업 날짜가 지나 취소한 신청
    left_confirmed: int            # 차감할 수 없어 확정으로 남긴 예약 (수강권 확인 필요)
    pending_cancel_requests: int   # 수업일이 지난 '취소 신청 중' (강사가 정해야 해서 건드리지 않는다)


class BulkCompleteRequest(BaseModel):
    """강사가 여러 예약을 한 번에 완료할 때 입력"""
    booking_ids: list[int] = Field(min_length=1, max_length=50)

    model_config = {"extra": "forbid"}


class BulkCompleteItem(BaseModel):
    """일괄 완료의 예약 한 건 결과. 안 된 건은 ok=False 와 화면에 보여 줄 이유(message)"""
    booking_id: int
    ok: bool
    status: str | None = None   # 처리 뒤의 예약 상태
    message: str | None = None


class BulkCompleteResponse(BaseModel):
    results: list[BulkCompleteItem]   # 처리한 순서 (레슨 날짜가 빠른 순)
    completed: int
    failed: int
