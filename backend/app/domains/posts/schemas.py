from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from app.domains.posts.models import PostType, PostStatus, MediaType, NotificationType, MatchStatus

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
    
    # 캘린더 연동 정보
    time_slot_id: Optional[int] = None
    when: Optional[date] = None

# 게시물 수정
class PostUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    status: Optional[PostStatus] = None
    
    time_slot_id: Optional[int] = None
    when: Optional[date] = None

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
    
    time_slot_id: Optional[int]
    when: Optional[date]
    
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

# 매칭 신청 요청
class MatchRequestCreate(BaseModel):
    post_id: UUID

# 매칭 신청 내역 응답
class MatchRequestRead(BaseModel):
    id: int
    post_id: UUID
    guest_id: UUID
    status: MatchStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# 매칭 결정 요청
class MatchDecision(BaseModel):
    match_request_id: int
    accept: bool