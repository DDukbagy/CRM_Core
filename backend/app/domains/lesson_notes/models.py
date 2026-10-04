from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy_utc import UtcDateTime
from sqlmodel import SQLModel, Field, func
from pydantic import AwareDatetime


class LessonNote(SQLModel, table=True):
    """
    강사가 고객에게 남기는 레슨 노트 (피드백 게시물을 여기로 통합, 2026-10-04)
    - 고객별로 자유롭게 작성. 특정 예약(레슨)에 연결하는 것은 선택 (예약당 최대 1개)
    - 앱에서 쓴 글(content) 또는 수기 노트를 스캔한 PDF(file_key) 중 하나 이상
    - is_shared=True 이면 고객이 레슨노트 탭에서 볼 수 있음
    """
    __tablename__ = "lesson_notes"
    __table_args__ = (
        CheckConstraint("content IS NOT NULL OR file_key IS NOT NULL", name="ck_lesson_notes_body"),
    )

    id: Optional[UUID] = Field(
        default=None,
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )

    customer_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        description="노트를 받는 고객 ID",
    )

    booking_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, unique=True),
        description="연결된 예약 ID (선택)",
    )

    instructor_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        description="작성한 강사 ID",
    )

    title: Optional[str] = Field(default=None, sa_type=Text, nullable=True, description="제목")

    content: Optional[str] = Field(default=None, sa_type=Text, nullable=True, description="레슨 노트 내용")

    # 스캔한 수기 노트 (PDF, S3 키). 응답에는 서명 주소(file_url)로 내보낸다
    file_key: Optional[str] = Field(default=None, sa_type=Text, nullable=True, description="첨부 PDF S3 키")
    file_name: Optional[str] = Field(default=None, sa_type=Text, nullable=True, description="첨부 파일 이름")

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
