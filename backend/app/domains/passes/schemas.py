from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ─── Pass Type ────────────────────────────────────────────────────────────────

class PassTypeCreate(BaseModel):
    name: str
    duration_hours: int
    session_count: int
    price: Optional[int] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PassTypeUpdate(BaseModel):
    name: Optional[str] = None
    duration_hours: Optional[int] = None
    session_count: Optional[int] = None
    price: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class PassTypeRead(BaseModel):
    id: int
    instructor_id: UUID
    name: str
    duration_hours: int
    session_count: int
    price: Optional[int] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Customer Pass ────────────────────────────────────────────────────────────

class CustomerPassAssign(BaseModel):
    """강사가 고객에게 수강권 발급"""
    customer_id: UUID
    pass_type_id: int
    price_paid: Optional[int] = None
    note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class CustomerPassUpdate(BaseModel):
    """수강권 상태/횟수 업데이트 (강사 전용)"""
    sessions_used: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class AddSessionsRequest(BaseModel):
    """강사 서비스: 기존 수강권에 횟수 추가"""
    sessions: int          # 추가할 횟수 (양수)
    note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class InstructorBrief(BaseModel):
    id: UUID
    display_name: str
    instructor_location: Optional[str] = None
    instructor_bio: Optional[str] = None
    instructor_specialties: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerPassRead(BaseModel):
    id: int
    pass_type_id: int
    customer_id: UUID
    instructor_id: UUID
    pass_name: str
    duration_hours: int
    sessions_total: int
    sessions_used: int
    sessions_remaining: int = 0   # router에서 계산해서 주입
    price_paid: Optional[int] = None
    status: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # 조회 시 enriched 필드
    instructor: Optional[InstructorBrief] = None
    pass_type: Optional[PassTypeRead] = None
    customer_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
