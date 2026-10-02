"""채팅: 참여자만 접근, 메시지 전송·읽음 처리, 방 목록의 마지막 메시지 시각"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import _ensure_instructor

pytestmark = pytest.mark.asyncio


async def _room(session: AsyncSession, customer_id: uuid.UUID, instructor_id: uuid.UUID) -> uuid.UUID:
    room_id = (
        await session.execute(
            text("insert into public.chat_rooms (customer_id, instructor_id) values (:c, :i) returning id"),
            {"c": str(customer_id), "i": str(instructor_id)},
        )
    ).scalar_one()
    await session.commit()
    return room_id


async def test_send_message_updates_room_and_marks_read(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        instructor = await _ensure_instructor(session)
        room_id = await _room(session, me, instructor)
        await session.execute(
            # 테스트는 한 트랜잭션 안이라 now()가 같으므로 먼저 온 메시지 시각을 앞당겨 둔다
            text(
                "insert into public.chat_messages (room_id, sender_id, content, created_at) "
                "values (:r, :s, '안녕하세요', now() - interval '1 minute')"
            ),
            {"r": str(room_id), "s": str(instructor)},
        )
        await session.commit()

    [room] = (await client.get("/chat/rooms")).json()
    assert room["unread_count"] == 1 and room["other_id"] == str(instructor)

    r = await client.post(f"/chat/rooms/{room_id}/messages", json={"content": "  레슨 문의드려요  "})
    assert r.status_code == 201, r.text
    assert r.json()["content"] == "레슨 문의드려요" and r.json()["is_mine"] is True

    # 방의 마지막 메시지 시각이 기록된다
    async with db_conn_and_sessionmaker() as session:
        last_at = (await session.execute(text("select last_message_at from public.chat_rooms where id = :r"), {"r": str(room_id)})).scalar_one()
    assert last_at is not None

    messages = (await client.get(f"/chat/rooms/{room_id}/messages")).json()
    assert [m["content"] for m in messages] == ["안녕하세요", "레슨 문의드려요"]
    [room] = (await client.get("/chat/rooms")).json()
    assert room["unread_count"] == 0 and room["last_message"] == "레슨 문의드려요"
    # 시각에 시간대(UTC)가 붙어 있어야 앱이 9시간 어긋나게 표시하지 않는다
    from datetime import datetime, timedelta, timezone
    for ts in (room["last_message_at"], room["created_at"], messages[-1]["created_at"], r.json()["created_at"]):
        parsed = datetime.fromisoformat(ts)
        assert parsed.utcoffset() == timedelta(0), ts
        assert abs(datetime.now(timezone.utc) - parsed) < timedelta(minutes=5), ts


async def test_only_participants_can_access_room(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    async with db_conn_and_sessionmaker() as session:
        instructor = await _ensure_instructor(session)
        other_customer = (await session.execute(
            text(
                """
                insert into public.users (id, username, display_name, is_active, status, role, feedback_consent)
                values (gen_random_uuid(), :u, 'other', true, 'ACTIVE', 'CUSTOMER', true) returning id
                """
            ),
            {"u": f"chat-{uuid.uuid4().hex[:8]}"},
        )).scalar_one()
        room_id = await _room(session, other_customer, instructor)

    assert (await client.get(f"/chat/rooms/{room_id}/messages")).status_code == 403
    assert (await client.post(f"/chat/rooms/{room_id}/messages", json={"content": "x"})).status_code == 403
    assert (await client.get(f"/chat/rooms/{uuid.uuid4()}/messages")).status_code == 404


@pytest.mark.parametrize("content, status", [("   ", 400), ("가" * 2001, 422)], ids=["blank", "too-long"])
async def test_invalid_message_is_rejected(client, db_conn_and_sessionmaker, content, status):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        room_id = await _room(session, me, await _ensure_instructor(session))
    r = await client.post(f"/chat/rooms/{room_id}/messages", json={"content": content})
    assert r.status_code == status, r.text


async def test_invalid_before_cursor_is_400(client, db_conn_and_sessionmaker):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        room_id = await _room(session, me, await _ensure_instructor(session))
    r = await client.get(f"/chat/rooms/{room_id}/messages", params={"before": "not-a-uuid"})
    assert r.status_code == 400, r.text
