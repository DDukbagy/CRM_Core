from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )