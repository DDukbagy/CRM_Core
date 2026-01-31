from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# models.py에 있는 Enum 가져오기
from app.domains.posts.models import PostType, PostStatus

# 1. 공통 속성 (Base)
class PostBase(BaseModel):
    title: Optional[str] = Field(None, title="게시글 제목")
    caption: Optional[str] = Field(None, title="게시글 내용")
    post_type: PostType = Field(default=PostType.COMMUNITY, title="게시글 유형")
    status: PostStatus = Field(default=PostStatus.PRIVATE, title="공개 상태")
    is_consent_given: bool = Field(default=False, title="고객 동의 여부")

# 2. 생성 요청 (Request) - 클라이언트가 보낼 데이터
class PostCreate(BaseModel):  # 상속 구조를 단순화하거나 Base를 써도 됨
    # 필수 필드
    owner_user_id: UUID = Field(..., title="게시글 주인(회원) ID")
    
    # 선택/기본값 필드 (Base 포함)
    title: Optional[str] = Field(None)
    caption: Optional[str] = Field(None)
    post_type: PostType = Field(default=PostType.COMMUNITY)
    status: PostStatus = Field(default=PostStatus.PRIVATE)
    is_consent_given: bool = Field(default=False)
    
    # 강사 ID (선택)
    instructor_id: Optional[UUID] = Field(None, title="담당 강사 ID")

# 3. 응답 데이터 (Response) - 클라이언트에게 줄 데이터
class PostResponse(PostBase):
    id: UUID
    owner_user_id: UUID
    created_by_user_id: Optional[UUID]
    instructor_id: Optional[UUID]
    
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    class Config:
        from_attributes = True # ORM 객체를 Pydantic 모델로 변환 허용