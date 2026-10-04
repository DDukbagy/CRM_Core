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
    type: str  # PROMOTION | NOTICE | FEEDBACK | COMMUNITY
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: list[MediaItemCreate] = []
    customer_id: Optional[UUID] = None
    # 콘텐츠 매니저가 대신 작성할 때의 대상 강사
    instructor_id: Optional[UUID] = None
    model_config = ConfigDict(extra="forbid")


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: Optional[list[MediaItemCreate]] = None  # None = 변경 없음
    model_config = ConfigDict(extra="forbid")


class PostRead(BaseModel):
    id: UUID
    instructor_id: UUID
    created_by_user_id: Optional[UUID] = None
    type: str
    title: Optional[str] = None
    content: Optional[str] = None
    media_items: list[MediaItemRead] = []
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    is_public: bool
    created_at: datetime
    updated_at: datetime

    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False

    model_config = ConfigDict(from_attributes=True)


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    fields: dict[str, str] = {}  # presigned PUT은 fields 없음
    key: str
    public_url: str


DELETED_COMMENT_TEXT = "삭제된 댓글입니다"


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


class CommentUpdate(BaseModel):
    content: str


class CommentRead(BaseModel):
    id: int
    post_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    parent_id: Optional[int] = None
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    # 삭제된 댓글이면 true. 이때 content는 DELETED_COMMENT_TEXT, user_name은 null
    is_deleted: bool = False
    model_config = ConfigDict(from_attributes=True)
