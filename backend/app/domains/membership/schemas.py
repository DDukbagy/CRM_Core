from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class MembershipCreate(BaseModel):
    customer_id: UUID
    type: str                          # TIMES | PERIOD
    total_count: Optional[int] = None  # TIMES 필수
    started_at: Optional[date] = None
    expires_at: Optional[date] = None  # PERIOD 필수
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_type_fields(self):
        if self.type == "TIMES":
            if self.total_count is None or self.total_count <= 0:
                raise ValueError("TIMES 타입은 total_count(양수)가 필요합니다.")
        elif self.type == "PERIOD":
            if not self.expires_at:
                raise ValueError("PERIOD 타입은 expires_at이 필요합니다.")
        else:
            raise ValueError("type은 TIMES 또는 PERIOD 이어야 합니다.")
        return self


class MembershipUpdate(BaseModel):
    is_active: Optional[bool] = None
    remaining_count: Optional[int] = None  # 강사가 수동 조정
    expires_at: Optional[date] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class MembershipRead(BaseModel):
    id: UUID
    customer_id: UUID
    instructor_id: UUID
    type: str
    total_count: Optional[int] = None
    remaining_count: Optional[int] = None
    started_at: Optional[date] = None
    expires_at: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
