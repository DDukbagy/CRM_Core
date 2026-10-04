from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field, func


# 게시물 종류 (DB에는 문자열로 저장, chk_posts_type 으로 제한)
class PostType(str, Enum):
    PROMOTION = "PROMOTION"   # 홍보 (공개)
    NOTICE = "NOTICE"         # 공지 (공개)
    FEEDBACK = "FEEDBACK"     # 피드백 (비공개: 작성 강사와 대상 고객만, 고객 동의 시 공개)
    COMMUNITY = "COMMUNITY"   # 커뮤니티 (공개)


# 미디어 파일 종류
class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


# 게시물 테이블
class Post(SQLModel, table=True):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('PROMOTION', 'NOTICE', 'FEEDBACK', 'COMMUNITY')", name="chk_posts_type"
        ),
    )

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # 게시물의 주인(강사 또는 관리자)
    instructor_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    # 실제 작성자 (콘텐츠 매니저가 강사 대신 작성한 경우 매니저)
    created_by_user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    type: str = Field(sa_column=Column(String(20), nullable=False))
    title: Optional[str] = Field(default=None, sa_type=String(200))
    content: Optional[str] = Field(default=None, sa_type=Text)
    # 단일 미디어 (레거시, 신규는 post_media 테이블 사용)
    media_url: Optional[str] = Field(default=None, sa_type=Text)
    media_type: Optional[str] = Field(default=None, sa_type=String(10))
    # FEEDBACK 대상 고객
    customer_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    is_public: bool = Field(default=False, index=True)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )


# 미디어 테이블
class PostMedia(SQLModel, table=True):
    __tablename__ = "post_media"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    post_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    url: str = Field(sa_type=Text)
    # S3 객체 키. 있으면 조회 시 임시 서명 URL을 발급한다.
    s3_key: Optional[str] = Field(default=None, sa_type=Text)
    media_type: str = Field(max_length=10)  # IMAGE | VIDEO
    sort_order: int = Field(default=0)


# 댓글 테이블 (parent_id 가 있으면 대댓글)
class PostComment(SQLModel, table=True):
    __tablename__ = "post_comments"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    post_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    user_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    parent_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    content: str = Field(sa_type=Text)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )
    # 삭제 시각. 값이 있으면 원문은 지워져 있고 목록에는 "삭제된 댓글입니다"로 보인다 (대댓글은 유지)
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


# 좋아요 테이블 (사용자당 게시물 1회)
class PostLike(SQLModel, table=True):
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_post_likes_user_post"),
    )

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    post_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    user_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
