from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel, func


# 선언은 실제 DB(마이그레이션 k5l6m7n8o9p0)에 맞춘다: 시각은 시간대 없는 timestamp, 외래키는 ON DELETE 동작 포함
class ChatRoom(SQLModel, table=True):
    __tablename__ = "chat_rooms"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    )
    customer_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    instructor_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    match_request_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("instructor_match_requests.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(), server_default=func.now(), nullable=False)
    )
    last_message_at: Optional[datetime] = Field(default=None, sa_type=DateTime())


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    )
    room_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    sender_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    content: str = Field(max_length=2000)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(
        sa_column=Column(DateTime(), server_default=func.now(), nullable=False)
    )
