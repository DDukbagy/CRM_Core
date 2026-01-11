from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field


class Post(SQLModel, table=True):
    __tablename__ = "posts"

    id: UUID = Field(
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    owner_user_id: UUID = Field(sa_type=PGUUID(as_uuid=True), nullable=False, index=True)
    created_by_user_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True)
    instructor_id: Optional[UUID] = Field(sa_type=PGUUID(as_uuid=True), nullable=True, index=True)

    caption: Optional[str] = Field(default=None)

    status: str = Field(default="PRIVATE", nullable=False, index=True)

    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("now()")},
        nullable=False,
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": text("now()")},
        nullable=False,
    )
    published_at: Optional[datetime] = Field(default=None, nullable=True)
