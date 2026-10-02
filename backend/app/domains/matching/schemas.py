from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
