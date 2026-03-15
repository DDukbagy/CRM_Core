from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MediaItemCreate(BaseModel):
    url: str
    media_type: str  # IMAGE | VIDEO
    sort_order: int = 0


class MediaItemRead(BaseModel):
    id: int
    url: str
    media_type: str
    sort_order: int
    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    type: str  # PROMOTION | FEEDBACK
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: list[MediaItemCreate] = []
    customer_id: Optional[UUID] = None
    model_config = ConfigDict(extra="forbid")


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: Optional[list[MediaItemCreate]] = None  # None = 변경 없음
    model_config = ConfigDict(extra="forbid")


class PostRead(BaseModel):
    id: UUID
    instructor_id: UUID
    type: str
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: list[MediaItemRead] = []
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    fields: dict[str, str] = {}  # presigned PUT은 fields 없음
    key: str
    public_url: str


class CommentCreate(BaseModel):
    content: str


class CommentRead(BaseModel):
    id: int
    post_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
