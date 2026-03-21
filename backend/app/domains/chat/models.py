from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel, func


class ChatRoom(SQLModel, table=True):
    __tablename__ = "chat_rooms"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    )
    customer_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="users.id", index=True)
    instructor_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="users.id", index=True)
    match_request_id: Optional[UUID] = Field(
        default=None, sa_type=PGUUID(as_uuid=True),
        foreign_key="instructor_match_requests.id", index=True
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    last_message_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    )
    room_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="chat_rooms.id", index=True)
    sender_id: UUID = Field(sa_type=PGUUID(as_uuid=True), foreign_key="users.id")
    content: str = Field(max_length=2000)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
