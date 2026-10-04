"""레슨 노트: 작성 권한(담당 고객 / 본인 캘린더 예약), 고객 공유 여부, 고객별 목록, PDF 첨부, 피드백 통합"""
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

    r = await instructor_client.post("/lesson-notes", json={"booking_id": booking_id, "content": "백스윙 교정", "is_shared": False})
    assert r.status_code == 201, r.text
    assert r.json()["is_shared"] is False and r.json()["customer_id"] == str(managed_customer_id)

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
            text("insert into public.lesson_notes (customer_id, booking_id, instructor_id, content, is_shared) values (:c, :b, :i, '노트', false)"),
            {"c": str(me), "b": booking_id, "i": str(host)},
        )
        await session.commit()

    assert (await client.get(f"/lesson-notes/booking/{booking_id}")).status_code == 403
    async with db_conn_and_sessionmaker() as session:
        await session.execute(text("update public.lesson_notes set is_shared = true where booking_id = :b"), {"b": booking_id})
        await session.commit()
    r = await client.get(f"/lesson-notes/booking/{booking_id}")
    assert r.status_code == 200 and r.json()["content"] == "노트"
    assert (await client.post("/lesson-notes", json={"booking_id": booking_id, "content": "x"})).status_code == 403


# ── 고객별 노트 (예약 연결 없이), PDF, 목록 (2026-10-04) ────────────────────

async def test_note_for_managed_customer_without_booking(instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker):
    r = await instructor_client.post("/lesson-notes", json={"customer_id": str(managed_customer_id), "title": "1회차", "content": "그립 교정"})
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["booking_id"] is None and note["is_shared"] is True and note["title"] == "1회차" and note["file_url"] is None

    # 수정·고객별 목록·삭제
    r = await instructor_client.patch(f"/lesson-notes/{note['id']}", json={"content": "그립·어드레스 교정"})
    assert r.status_code == 200 and r.json()["content"] == "그립·어드레스 교정"
    listed = (await instructor_client.get(f"/lesson-notes?customer_id={managed_customer_id}")).json()
    assert [n["id"] for n in listed] == [note["id"]] and listed[0]["customer_name"]
    assert (await instructor_client.delete(f"/lesson-notes/{note['id']}")).status_code == 204
    assert (await instructor_client.get(f"/lesson-notes/{note['id']}")).status_code == 404


async def test_note_rules(instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker):
    from tests.conftest import insert_user

    async with db_conn_and_sessionmaker() as session:
        stranger = await insert_user(session, "CUSTOMER")
    # 담당 고객이 아니면 403, 대상 없음 400, 내용·PDF 둘 다 없음 400
    assert (await instructor_client.post("/lesson-notes", json={"customer_id": str(stranger), "content": "x"})).status_code == 403
    assert (await instructor_client.post("/lesson-notes", json={"content": "x"})).status_code == 400
    assert (await instructor_client.post("/lesson-notes", json={"customer_id": str(managed_customer_id)})).status_code == 400
    # 다른 강사 경로의 파일은 붙일 수 없다
    r = await instructor_client.post("/lesson-notes", json={"customer_id": str(managed_customer_id), "file_key": "lesson-notes/someone/x.pdf"})
    assert r.status_code == 400
    # 본인 경로의 PDF 만으로도 작성 가능 (응답에는 서명 주소 자리가 생김)
    r = await instructor_client.post("/lesson-notes", json={
        "customer_id": str(managed_customer_id), "file_key": f"lesson-notes/{instructor_id}/scan.pdf", "file_name": "scan.pdf"})
    assert r.status_code == 201 and r.json()["file_name"] == "scan.pdf"


async def test_upload_url_only_pdf(instructor_client):
    r = await instructor_client.post("/lesson-notes/upload-url", json={"filename": "a.jpg", "content_type": "image/jpeg"})
    assert r.status_code == 400
    # 로컬 테스트에는 S3 설정이 없어 503 (설정이 있으면 200 + upload_url)
    r = await instructor_client.post("/lesson-notes/upload-url", json={"filename": "note.pdf"})
    assert r.status_code in (200, 503)


async def test_customer_lists_only_own_shared_notes(client, db_conn_and_sessionmaker):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        host = await _ensure_instructor(session)
        for shared, body in ((True, "공유됨"), (False, "비공개")):
            await session.execute(
                text("insert into public.lesson_notes (customer_id, instructor_id, content, is_shared) values (:c, :i, :b, :s)"),
                {"c": str(me), "i": str(host), "b": body, "s": shared},
            )
        await session.commit()
    notes = (await client.get("/lesson-notes")).json()
    assert [n["content"] for n in notes] == ["공유됨"] and notes[0]["instructor_name"]

