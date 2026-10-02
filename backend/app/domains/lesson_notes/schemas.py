from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LessonNoteCreate(BaseModel):
    booking_id: int
    content: str
    is_shared: bool = False
    model_config = ConfigDict(extra="forbid")


class LessonNoteUpdate(BaseModel):
    content: str | None = None
    is_shared: bool | None = None
    model_config = ConfigDict(extra="forbid")


class LessonNoteRead(BaseModel):
    id: UUID
    booking_id: int
    instructor_id: UUID
    content: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
