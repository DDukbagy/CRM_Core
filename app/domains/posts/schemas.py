from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel


# 1. Enum 정의 (DB와 일치시킴)
class PostType(str, Enum):
    NOTICE = "NOTICE"
    COMMUNITY = "COMMUNITY"
    FEEDBACK = "FEEDBACK"


class PostStatus(str, Enum):
    PUBLIC = "PUBLIC"
    MEMBERS = "MEMBERS"
    PRIVATE = "PRIVATE"


# 2. 생성 요청 스키마 (Admin용)
class PostCreateAdmin(BaseModel):
    owner_user_id: UUID
    title: str | None = None 
    caption: str | None = None
    
    post_type: PostType = PostType.COMMUNITY
    status: PostStatus = PostStatus.PRIVATE
    is_consent_given: bool = False
    
    # 강사/스태프가 만든 post면 스코프 고정용
    instructor_id: UUID | None = None

    model_config = {"extra": "forbid"}


# 3. 조회 응답 스키마
class PostRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    created_by_user_id: UUID | None
    instructor_id: UUID | None
    
    title: str | None 
    caption: str | None
    
    post_type: PostType 
    status: PostStatus 
    is_consent_given: bool 
    
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}