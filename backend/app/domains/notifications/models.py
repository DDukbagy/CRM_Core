from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field

# 알림 종류
class NotificationType(str, Enum):
    LIKE = "LIKE"
    COMMENT = "COMMENT"
    REPLY = "REPLY"
    SYSTEM = "SYSTEM"

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
