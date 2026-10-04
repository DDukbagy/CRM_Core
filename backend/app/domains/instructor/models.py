from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import text, ForeignKey
from sqlmodel import SQLModel, Field, func


class InstructorStaff(SQLModel, table=True):
    __tablename__ = "instructor_staff"
    __table_args__ = (
        UniqueConstraint("instructor_id", "staff_user_id", name="instructor_staff_instructor_id_staff_user_id_key"),
        {"extend_existing": True},
    )

    # 원격 DB 와 같은 UUID (DB 가 생성)
    id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    )
    instructor_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    staff_user_id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
