from enum import Enum
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

from sqlalchemy import Column, DateTime, func, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field, Relationship
from pydantic import ConfigDict

# 게시물 종류
class PostType(str, Enum):
    NOTICE = "NOTICE"
    COMMUNITY = "COMMUNITY"
    FEEDBACK = "FEEDBACK"

# 공개 상태
class PostStatus(str, Enum):
    PUBLIC = "PUBLIC"
    MEMBERS = "MEMBERS"
    PRIVATE = "PRIVATE"

# 미디어 파일 종류
class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"

# 알림 종류
class NotificationType(str, Enum):
    LIKE = "LIKE"
    COMMENT = "COMMENT"
    REPLY = "REPLY"
    SYSTEM = "SYSTEM"

# 매칭 상태
class MatchStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

# 미디어 테이블
class PostMedia(SQLModel, table=True):
    __tablename__ = "post_media"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    post_id: UUID = Field(foreign_key="posts.id", nullable=False, index=True)
    media_type: MediaType = Field(default=MediaType.IMAGE)
    url: str = Field(nullable=False)
    s3_key_source: str = Field(nullable=False)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    post: "Post" = Relationship(back_populates="media")

# 댓글 테이블
class Comment(SQLModel, table=True):
    __tablename__ = "comments"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    post_id: UUID = Field(foreign_key="posts.id", nullable=False, index=True)
    user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)
    parent_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), index=True)
    
    content: str = Field(nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )

    post: "Post" = Relationship(back_populates="comments")

# 좋아요 테이블
class PostLike(SQLModel, table=True):
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),
    )

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    post_id: UUID = Field(foreign_key="posts.id", nullable=False, index=True)
    user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    post: "Post" = Relationship(back_populates="likes")

# 알림 테이블
class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    recipient_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)
    sender_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True)
    
    notification_type: NotificationType = Field(nullable=False)
    related_post_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True)
    content: Optional[str] = Field(default=None)
    
    is_read: bool = Field(default=False)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

# 매칭 신청 테이블
class MatchRequest(SQLModel, table=True):
    __tablename__ = "match_requests"
    __table_args__ = (
        UniqueConstraint("post_id", "guest_id", name="uq_post_guest_application"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    post_id: UUID = Field(foreign_key="posts.id", index=True)
    guest_id: UUID = Field(foreign_key="users.id", index=True)
    
    status: MatchStatus = Field(default=MatchStatus.PENDING)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

# 게시물 테이블
class Post(SQLModel, table=True):
    model_config = ConfigDict(extra="allow")

    __tablename__ = "posts"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    owner_user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)
    created_by_user_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True)
    instructor_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True, index=True)

    title: Optional[str] = Field(default=None)
    caption: Optional[str] = Field(default=None)
    
    post_type: PostType = Field(default=PostType.COMMUNITY, index=True)
    status: PostStatus = Field(default=PostStatus.PRIVATE, nullable=False, index=True)
    is_consent_given: bool = Field(default=False)

    # 캘린더 연동 필드
    time_slot_id: Optional[int] = Field(default=None)
    when: Optional[date] = Field(default=None)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )
    published_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    media: List["PostMedia"] = Relationship(back_populates="post", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    comments: List["Comment"] = Relationship(back_populates="post", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    likes: List["PostLike"] = Relationship(back_populates="post", sa_relationship_kwargs={"cascade": "all, delete-orphan"})