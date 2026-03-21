from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.chat.models import ChatRoom, ChatMessage
from app.domains.chat.schemas import ChatRoomRead, ChatMessageCreate, ChatMessageRead
from app.domains.users.models import User

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/rooms", response_model=list[ChatRoomRead])
async def list_my_rooms(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """내 채팅방 목록 (강사/고객 모두)"""
    uid = UUID(str(user.id))
    res = await session.execute(
        select(ChatRoom).where(
            or_(ChatRoom.customer_id == uid, ChatRoom.instructor_id == uid)
        ).order_by(ChatRoom.last_message_at.desc().nullslast(), ChatRoom.created_at.desc())
    )
    rooms = res.scalars().all()

    result = []
    for room in rooms:
        is_customer = room.customer_id == uid
        other_id = room.instructor_id if is_customer else room.customer_id

        other_res = await session.execute(select(User).where(User.id == other_id))
        other = other_res.scalar_one_or_none()

        # 마지막 메시지
        last_msg_res = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == room.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_res.scalar_one_or_none()

        # 안 읽은 메시지 수
        unread_res = await session.execute(
            select(func.count()).where(
                and_(
                    ChatMessage.room_id == room.id,
                    ChatMessage.sender_id != uid,
                    ChatMessage.is_read == False,
                )
            )
        )
        unread_count = unread_res.scalar() or 0

        result.append(ChatRoomRead(
            id=room.id,
            customer_id=room.customer_id,
            instructor_id=room.instructor_id,
            match_request_id=room.match_request_id,
            other_name=other.display_name if other else "알 수 없음",
            other_id=other_id,
            last_message=last_msg.content if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else room.last_message_at,
            unread_count=unread_count,
            created_at=room.created_at,
        ))
    return result


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    room_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None, description="이 메시지 ID 이전 목록 (페이지네이션)"),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """채팅방 메시지 목록 (폴링용)"""
    uid = UUID(str(user.id))
    room = await _get_room_or_403(session, room_id, uid)

    stmt = select(ChatMessage).where(ChatMessage.room_id == room.id)
    if before:
        before_msg = await session.get(ChatMessage, UUID(before))
        if before_msg:
            stmt = stmt.where(ChatMessage.created_at < before_msg.created_at)

    stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    messages = list(reversed(res.scalars().all()))

    # 읽음 처리 (상대방 메시지만)
    await session.execute(
        update(ChatMessage)
        .where(
            and_(
                ChatMessage.room_id == room.id,
                ChatMessage.sender_id != uid,
                ChatMessage.is_read == False,
            )
        )
        .values(is_read=True)
    )
    await session.commit()

    return [
        ChatMessageRead(
            id=m.id,
            room_id=m.room_id,
            sender_id=m.sender_id,
            content=m.content,
            is_read=m.is_read,
            is_mine=m.sender_id == uid,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageRead, status_code=201)
async def send_message(
    room_id: UUID,
    payload: ChatMessageCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """메시지 전송"""
    uid = UUID(str(user.id))
    room = await _get_room_or_403(session, room_id, uid)

    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="메시지 내용을 입력하세요.")

    msg = ChatMessage(
        room_id=room.id,
        sender_id=uid,
        content=payload.content.strip(),
    )
    session.add(msg)

    room.last_message_at = msg.created_at
    session.add(room)

    await session.commit()
    await session.refresh(msg)

    return ChatMessageRead(
        id=msg.id,
        room_id=msg.room_id,
        sender_id=msg.sender_id,
        content=msg.content,
        is_read=msg.is_read,
        is_mine=True,
        created_at=msg.created_at,
    )


async def _get_room_or_403(session: AsyncSession, room_id: UUID, user_id: UUID) -> ChatRoom:
    room = await session.get(ChatRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    if room.customer_id != user_id and room.instructor_id != user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    return room
