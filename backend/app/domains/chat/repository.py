from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.models import ChatMessage, ChatRoom
from app.domains.users.models import User


@dataclass
class RoomSummary:
    room: ChatRoom
    other_id: UUID
    other_name: str
    last_message: Optional[ChatMessage]
    unread_count: int


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_room_for_member(self, room_id: UUID, user_id: UUID) -> ChatRoom:
        """채팅방 참여자(고객·강사)만 접근"""
        room = await self.session.get(ChatRoom, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        if room.customer_id != user_id and room.instructor_id != user_id:
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
        return room

    # 내 채팅방 목록: 상대 이름, 마지막 메시지, 안 읽은 수 (최근 대화 순)
    async def list_rooms(self, user_id: UUID) -> list[RoomSummary]:
        rooms = (
            await self.session.execute(
                select(ChatRoom)
                .where(or_(ChatRoom.customer_id == user_id, ChatRoom.instructor_id == user_id))
                .order_by(ChatRoom.last_message_at.desc().nullslast(), ChatRoom.created_at.desc())
            )
        ).scalars().all()

        result: list[RoomSummary] = []
        for room in rooms:
            other_id = room.instructor_id if room.customer_id == user_id else room.customer_id
            other = (await self.session.execute(select(User).where(User.id == other_id))).scalar_one_or_none()
            last_msg = (
                await self.session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.room_id == room.id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            unread = (
                await self.session.execute(
                    select(func.count()).where(
                        and_(
                            ChatMessage.room_id == room.id,
                            ChatMessage.sender_id != user_id,
                            ChatMessage.is_read == False,  # noqa: E712
                        )
                    )
                )
            ).scalar() or 0
            result.append(RoomSummary(room, other_id, other.display_name if other else "알 수 없음", last_msg, unread))
        return result

    # 메시지 목록 (before 메시지보다 이전 것, 오래된 순) + 상대 메시지 읽음 처리
    async def list_messages(self, room: ChatRoom, user_id: UUID, limit: int, before: Optional[str]) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.room_id == room.id)
        if before:
            try:
                before_id = UUID(before)
            except ValueError:
                raise HTTPException(status_code=400, detail="before 는 메시지 ID(UUID)여야 합니다.")
            before_msg = await self.session.get(ChatMessage, before_id)
            if before_msg:
                stmt = stmt.where(ChatMessage.created_at < before_msg.created_at)

        stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)
        messages = list(reversed((await self.session.execute(stmt)).scalars().all()))

        await self.session.execute(
            update(ChatMessage)
            .where(
                and_(
                    ChatMessage.room_id == room.id,
                    ChatMessage.sender_id != user_id,
                    ChatMessage.is_read == False,  # noqa: E712
                )
            )
            .values(is_read=True)
        )
        await self.session.commit()
        return messages

    async def send(self, room: ChatRoom, sender_id: UUID, content: str) -> ChatMessage:
        if not content.strip():
            raise HTTPException(status_code=400, detail="메시지 내용을 입력하세요.")
        msg = ChatMessage(room_id=room.id, sender_id=sender_id, content=content.strip())
        self.session.add(msg)
        # created_at 은 DB가 채우므로 flush 로 먼저 받아 와야 방의 마지막 메시지 시각에 쓸 수 있다
        await self.session.flush()
        await self.session.refresh(msg)
        room.last_message_at = msg.created_at
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def ensure_room_for_match(self, customer_id: UUID, instructor_id: UUID, match_request_id: UUID) -> None:
        """매칭 수락 시 채팅방 생성 (이미 있으면 그대로). commit 은 호출한 쪽에서"""
        existing = await self.session.execute(
            select(ChatRoom).where(
                and_(
                    ChatRoom.customer_id == customer_id,
                    ChatRoom.instructor_id == instructor_id,
                    ChatRoom.match_request_id == match_request_id,
                )
            )
        )
        if not existing.scalar_one_or_none():
            self.session.add(
                ChatRoom(customer_id=customer_id, instructor_id=instructor_id, match_request_id=match_request_id)
            )
