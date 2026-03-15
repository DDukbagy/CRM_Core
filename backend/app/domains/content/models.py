from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Text, String, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import text
from sqlmodel import SQLModel, Field, func


class InstructorPost(SQLModel, table=True):
    __tablename__ = "instructor_posts"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    instructor_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, foreign_key="users.id")
    type: str = Field(max_length=20)  # PROMOTION | FEEDBACK
    title: Optional[str] = Field(default=None, sa_type=String(200))
    content: Optional[str] = Field(default=None, sa_type=Text)
    # 단일 미디어 (레거시, 신규는 post_media 테이블 사용)
    media_url: Optional[str] = Field(default=None, sa_type=Text)
    media_type: Optional[str] = Field(default=None, sa_type=String(10))
    customer_id: Optional[UUID] = Field(default=None, sa_type=PGUUID(as_uuid=True), foreign_key="users.id", nullable=True)
    is_public: bool = Field(default=False)

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


class InstructorPostMedia(SQLModel, table=True):
    __tablename__ = "instructor_post_media"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    post_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="instructor_posts.id")
    url: str = Field(sa_type=Text)
    media_type: str = Field(max_length=10)  # IMAGE | VIDEO
    sort_order: int = Field(default=0)


class PostComment(SQLModel, table=True):
    __tablename__ = "post_comments"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    post_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="instructor_posts.id")
    user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="users.id")
    content: str = Field(sa_type=Text)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
