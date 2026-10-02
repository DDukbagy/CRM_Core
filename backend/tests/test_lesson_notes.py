"""레슨 노트: 작성 권한(본인 캘린더 예약만), 고객 공유 여부"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import _ensure_instructor

pytestmark = pytest.mark.asyncio


async def _booking_for_host(
    session: AsyncSession, host_id: uuid.UUID, guest_id: uuid.UUID, status: str = "CONFIRMED"
) -> int:
    calendar_id = (
        await session.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[]'::jsonb, 'c', :h) returning id"),
            {"h": str(host_id)},
        )
    ).scalar_one()
    slot_id = (
        await session.execute(
            text(
                """
                insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)
                values ('09:00'::time, '10:00'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id
                """
            ),
            {"c": calendar_id},
        )
    ).scalar_one()
    booking_id = (
        await session.execute(
            text(
                """
                insert into public.bookings ("when", topic, type, status, time_slot_id, guest_id)
                values (:d, '레슨', 'LESSON', :st, :s, :g) returning id
                """
            ),
            {"d": date.today() + timedelta(days=1), "st": status, "s": slot_id, "g": str(guest_id)},
        )
    ).scalar_one()
    await session.commit()
    return booking_id


async def test_instructor_writes_and_updates_note_on_own_booking(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        booking_id = await _booking_for_host(session, instructor_id, managed_customer_id)

    r = await instructor_client.post("/lesson-notes", json={"booking_id": booking_id, "content": "백스윙 교정"})
    assert r.status_code == 201, r.text
    assert r.json()["is_shared"] is False

    assert (await instructor_client.post("/lesson-notes", json={"booking_id": booking_id, "content": "x"})).status_code == 409
    r = await instructor_client.patch(f"/lesson-notes/booking/{booking_id}", json={"is_shared": True})
    assert r.status_code == 200 and r.json()["is_shared"] is True
    assert (await instructor_client.get(f"/lesson-notes/booking/{booking_id}")).json()["content"] == "백스윙 교정"


async def test_cannot_write_note_on_other_instructors_booking(
    instructor_client, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        other = await _ensure_instructor(session)
        booking_id = await _booking_for_host(session, other, managed_customer_id)

    r = await instructor_client.post("/lesson-notes", json={"booking_id": booking_id, "content": "남의 레슨"})
    assert r.status_code == 403, r.text


async def test_note_only_for_confirmed_or_completed(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        booking_id = await _booking_for_host(session, instructor_id, managed_customer_id, status="REQUESTED")
    r = await instructor_client.post("/lesson-notes", json={"booking_id": booking_id, "content": "x"})
    assert r.status_code == 400, r.text


async def test_customer_sees_note_only_when_shared(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        host = await _ensure_instructor(session)
        booking_id = await _booking_for_host(session, host, me)
        await session.execute(
            text("insert into public.lesson_notes (booking_id, instructor_id, content, is_shared) values (:b, :i, '노트', false)"),
            {"b": booking_id, "i": str(host)},
        )
        await session.commit()

    assert (await client.get(f"/lesson-notes/booking/{booking_id}")).status_code == 403
    async with db_conn_and_sessionmaker() as session:
        await session.execute(text("update public.lesson_notes set is_shared = true where booking_id = :b"), {"b": booking_id})
        await session.commit()
    r = await client.get(f"/lesson-notes/booking/{booking_id}")
    assert r.status_code == 200 and r.json()["content"] == "노트"
    assert (await client.post("/lesson-notes", json={"booking_id": booking_id, "content": "x"})).status_code == 403
