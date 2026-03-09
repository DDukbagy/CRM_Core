from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class InstructorStaffCreate(BaseModel):
    staff_email: EmailStr


class InstructorStaffRead(BaseModel):
    staff_user_id: UUID
    email: EmailStr | None
    username: str
    display_name: str
    created_at: datetime


# ── 강사 공개 프로필 ────────────────────────────────────────
class InstructorPublicRead(BaseModel):
    id: UUID
    display_name: str
    username: str
    instructor_tier: str            # NORMAL | NAMED
    match_fee: int                  # 0 or 5000
    is_active: bool
    location: Optional[str] = None
    specialties: list[str] = []     # 파싱된 스타일 태그 목록
    bio: Optional[str] = None


# ── 매칭/상담 요청 ──────────────────────────────────────────
class MatchRequestCreate(BaseModel):
    instructor_id: UUID
    note: Optional[str] = None
    request_type: str = "MATCH"   # MATCH | CONSULTATION


class MatchRequestRead(BaseModel):
    id: UUID
    customer_id: UUID
    instructor_id: UUID
    request_type: str = "MATCH"
    status: str                   # PENDING | ACCEPTED | REJECTED | CANCELLED
    fee: int
    note: Optional[str]
    instructor_name: Optional[str] = None
    customer_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
