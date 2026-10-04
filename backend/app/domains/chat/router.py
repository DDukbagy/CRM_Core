from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.chat.models import ChatMessage
from app.domains.chat.repository import ChatRepository
from app.domains.chat.schemas import ChatRoomRead, ChatRoomOpen, ChatMessageCreate, ChatMessageRead

router = APIRouter(prefix="/chat", tags=["Chat"])


def _message_read(m: ChatMessage, uid: UUID) -> ChatMessageRead:
    return ChatMessageRead(
        id=m.id, room_id=m.room_id, sender_id=m.sender_id, content=m.content,
        is_read=m.is_read, is_mine=m.sender_id == uid, created_at=m.created_at,
    )


@router.get("/rooms", response_model=list[ChatRoomRead])
async def list_my_rooms(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """내 채팅방 목록 (강사/고객 모두)"""
    summaries = await ChatRepository(session).list_rooms(UUID(str(user.id)))
    return [
        ChatRoomRead(
            id=s.room.id,
            customer_id=s.room.customer_id,
            instructor_id=s.room.instructor_id,
            match_request_id=s.room.match_request_id,
            other_name=s.other_name,
            other_id=s.other_id,
            last_message=s.last_message.content if s.last_message else None,
            last_message_at=s.last_message.created_at if s.last_message else s.room.last_message_at,
            unread_count=s.unread_count,
            created_at=s.room.created_at,
        )
        for s in summaries
    ]


@router.post("/rooms", response_model=ChatRoomRead)
async def open_inquiry_room(
    payload: ChatRoomOpen,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """고객 → 강사 문의하기: 채팅방을 열고(이미 있으면 그 방) 돌려준다"""
    uid = UUID(str(user.id))
    repo = ChatRepository(session)
    room = await repo.open_inquiry(uid, payload.instructor_id)
    s = next(s for s in await repo.list_rooms(uid) if s.room.id == room.id)
    return ChatRoomRead(
        id=room.id, customer_id=room.customer_id, instructor_id=room.instructor_id, match_request_id=room.match_request_id,
        other_name=s.other_name, other_id=s.other_id,
        last_message=s.last_message.content if s.last_message else None,
        last_message_at=s.last_message.created_at if s.last_message else room.last_message_at,
        unread_count=s.unread_count, created_at=room.created_at,
    )


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    room_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None, description="이 메시지 ID 이전 목록 (페이지네이션)"),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """채팅방 메시지 목록 (폴링용). 상대 메시지는 읽음 처리"""
    uid = UUID(str(user.id))
    repo = ChatRepository(session)
    room = await repo.get_room_for_member(room_id, uid)
    return [_message_read(m, uid) for m in await repo.list_messages(room, uid, limit, before)]


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageRead, status_code=201)
async def send_message(
    room_id: UUID,
    payload: ChatMessageCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """메시지 전송"""
    uid = UUID(str(user.id))
    repo = ChatRepository(session)
    room = await repo.get_room_for_member(room_id, uid)
    return _message_read(await repo.send(room, uid, payload.content), uid)
