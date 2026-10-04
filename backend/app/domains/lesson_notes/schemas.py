from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LessonNoteCreate(BaseModel):
    """customer_id 또는 booking_id 중 하나는 필요 (booking 이면 그 예약의 고객). 내용·PDF 중 하나 이상"""
    customer_id: UUID | None = None
    booking_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    file_key: str | None = None      # /lesson-notes/upload-url 로 올린 PDF 의 key
    file_name: str | None = Field(default=None, max_length=200)
    is_shared: bool = True           # 고객이 바로 볼 수 있게 (피드백과 같은 동작)
    model_config = ConfigDict(extra="forbid")


class LessonNoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    file_key: str | None = None
    file_name: str | None = Field(default=None, max_length=200)
    is_shared: bool | None = None
    model_config = ConfigDict(extra="forbid")


class LessonNoteRead(BaseModel):
    id: UUID
    customer_id: UUID
    booking_id: int | None = None
    instructor_id: UUID
    title: str | None = None
    content: str | None = None
    file_name: str | None = None
    file_url: str | None = None      # 첨부 PDF 서명 주소 (1시간)
    is_shared: bool
    customer_name: str | None = None
    instructor_name: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LessonNoteUploadRequest(BaseModel):
    filename: str = Field(max_length=200)
    content_type: str = "application/pdf"


class LessonNoteUploadResponse(BaseModel):
    upload_url: str
    key: str
