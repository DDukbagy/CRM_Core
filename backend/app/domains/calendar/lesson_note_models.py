from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import SQLModel, Field, func
from pydantic import AwareDatetime


class LessonNote(SQLModel, table=True):
    """
    강사가 예약(레슨)별로 작성하는 노트.
    - is_shared=True 이면 고객도 조회 가능
    - 예약당 1개 (UNIQUE booking_id)
    """
    __tablename__ = "lesson_notes"

    id: Optional[UUID] = Field(
        default=None,
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": "gen_random_uuid()"},
    )

    booking_id: int = Field(
        foreign_key="bookings.id",
        nullable=False,
        unique=True,
        description="연결된 예약 ID",
    )

    instructor_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
        description="작성한 강사 ID",
    )

    content: str = Field(
        sa_type=Text,
        nullable=False,
        description="레슨 노트 내용",
    )

    is_shared: bool = Field(
        default=False,
        sa_type=Boolean,
        nullable=False,
        description="고객 공유 여부",
    )

    created_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )
