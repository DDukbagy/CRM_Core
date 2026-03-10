from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Text, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import text, ForeignKey
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
    media_url: Optional[str] = Field(default=None, sa_type=Text)
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
