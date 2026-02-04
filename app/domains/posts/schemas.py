from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from app.domains.posts.models import PostType, PostStatus, MediaType, NotificationType

# 댓글 생성
class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[UUID] = None

# 댓글 수정
class CommentUpdate(BaseModel):
    content: str

# 댓글 응답
class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    parent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# 미디어 응답
class PostMediaResponse(BaseModel):
    id: UUID
    url: str
    media_type: MediaType
    sort_order: int
    s3_key_source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# 게시물 생성
class PostCreate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    post_type: PostType = PostType.COMMUNITY
    status: PostStatus = PostStatus.PRIVATE
    instructor_id: Optional[UUID] = None

# 게시물 수정
class PostUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    status: Optional[PostStatus] = None

# 게시물 상세 응답
class PostResponse(BaseModel):
    id: UUID
    owner_user_id: UUID
    created_by_user_id: Optional[UUID]
    instructor_id: Optional[UUID]
    
    title: Optional[str]
    caption: Optional[str]
    
    post_type: PostType
    status: PostStatus
    is_consent_given: bool
    
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    media: List[PostMediaResponse] = []
    
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False

    model_config = ConfigDict(from_attributes=True)

# 알림 응답
class NotificationResponse(BaseModel):
    id: UUID
    recipient_id: UUID
    sender_id: Optional[UUID]
    notification_type: NotificationType
    related_post_id: Optional[UUID]
    content: Optional[str]
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)