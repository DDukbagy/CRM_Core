from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ChatRoomRead(BaseModel):
    id: UUID
    customer_id: UUID
    instructor_id: UUID
    match_request_id: Optional[UUID]
    other_name: str
    other_id: UUID
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageRead(BaseModel):
    id: UUID
    room_id: UUID
    sender_id: UUID
    content: str
    is_read: bool
    is_mine: bool
    created_at: datetime

    model_config = {"from_attributes": True}
