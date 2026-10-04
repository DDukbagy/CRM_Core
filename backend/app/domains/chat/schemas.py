from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field


def _as_utc(v: datetime | None) -> datetime | None:
    """채팅 테이블은 시간대 없는 timestamp(DB 시간대 UTC)로 저장한다.
    응답에 시간대를 붙이지 않으면 앱이 기기 시간(한국)으로 해석해 9시간 어긋난다."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class ChatRoomRead(BaseModel):
    id: UUID
    customer_id: UUID
    instructor_id: UUID
    match_request_id: Optional[UUID]
    other_name: str
    other_id: UUID
    last_message: Optional[str]
    last_message_at: Optional[UtcDatetime]
    unread_count: int
    created_at: UtcDatetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str = Field(max_length=2000)  # chat_messages.content VARCHAR(2000)


class ChatMessageRead(BaseModel):
    id: UUID
    room_id: UUID
    sender_id: UUID
    content: str
    is_read: bool
    is_mine: bool
    created_at: UtcDatetime

    model_config = {"from_attributes": True}


class ChatRoomOpen(BaseModel):
    """강사에게 문의하기 → 그 강사와의 채팅방"""
    instructor_id: UUID
