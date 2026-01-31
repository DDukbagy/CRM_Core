from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field

class PostType(str, Enum):
    NOTICE = "NOTICE"
    COMMUNITY = "COMMUNITY"
    FEEDBACK = "FEEDBACK"

class PostStatus(str, Enum):
    PUBLIC = "PUBLIC"
    MEMBERS = "MEMBERS"
    PRIVATE = "PRIVATE"

class Post(SQLModel, table=True):
    __tablename__ = "posts"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    # 작성자 및 관계
    owner_user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)
    created_by_user_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True)
    instructor_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True, index=True)

    # 게시물 내용
    title: Optional[str] = Field(default=None)
    caption: Optional[str] = Field(default=None)
    
    # 게시물 설정
    post_type: PostType = Field(default=PostType.COMMUNITY, index=True)
    status: PostStatus = Field(default=PostStatus.PRIVATE, nullable=False, index=True)

    # 고객 동의 여부 (True 시 공개 전환 가능)
    is_consent_given: bool = Field(default=False)

    # 타임스탬프
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), 
            server_default=func.now(), 
            nullable=False
        )
    )

    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

    published_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), 
            nullable=True
        ),
    )