"""캘린더: 슬롯 전역 ON/OFF 와 날짜별 시간 닫기(CalendarBlock)의 적용 범위

회귀 방지 대상: "특정 날짜의 시간 휴무"가 TimeSlot.is_active 를 꺼서 모든 날짜에 적용되던 결함
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import _ensure_instructor

ALL_WEEKDAYS = "[0,1,2,3,4,5,6]"
DAY = date.today() + timedelta(days=7)        # 막을 날짜
NEXT_WEEK = DAY + timedelta(days=7)           # 같은 요일, 다음 주


async def _create_calendar_with_slots(session: AsyncSession, host_id: uuid.UUID) -> tuple[int, int, int]:
    calendar_id = (
        await session.execute(
            text(
                """
                insert into public.calendars (topics, description, host_id)
                values (CAST('["테스트"]' AS jsonb), '테스트 캘린더', :host_id)
                returning id
                """
            ),
            {"host_id": str(host_id)},
        )
    ).scalar_one()
    slot_ids = []
    for start, end in (("09:00", "10:00"), ("10:00", "11:00")):
        slot_ids.append(
            (
                await session.execute(
                    text(
                        f"""
                        insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)
                        values ('{start}'::time, '{end}'::time, '{ALL_WEEKDAYS}'::jsonb, true, :calendar_id)
                        returning id
                        """
                    ),
                    {"calendar_id": calendar_id},
                )
            ).scalar_one()
        )
    await session.commit()
    return calendar_id, slot_ids[0], slot_ids[1]


@pytest_asyncio.fixture
async def my_calendar(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession], instructor_id) -> tuple[int, int, int]:
    """instructor_client 사용자의 캘린더와 슬롯 2개 (매일 09시, 10시)"""
    async with db_conn_and_sessionmaker() as session:
        return await _create_calendar_with_slots(session, instructor_id)


@pytest_asyncio.fixture
async def other_calendar(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, int, int, int]:
    """다른 강사의 캘린더와 슬롯 2개"""
    async with db_conn_and_sessionmaker() as session:
        host_id = await _ensure_instructor(session)
        return (host_id, *await _create_calendar_with_slots(session, host_id))


async def _available_slot_ids(ac, host_id, day: date) -> list[int]:
    r = await ac.get(f"/calendars/{host_id}/availability", params={"start": day.isoformat(), "end": day.isoformat()})
    assert r.status_code == 200, r.text
    return [s["time_slot_id"] for s in r.json()["days"][0]["slots"]]


# ── 날짜별 시간 닫기 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_block_closes_slot_only_on_that_date(instructor_client, instructor_id, my_calendar):
    _, slot_a, slot_b = my_calendar

    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat(), "time_slot_ids": [slot_a]})
    assert r.status_code == 201, r.text
    [block] = r.json()
    assert block["time_slot_id"] == slot_a and block["start_date"] == block["end_date"] == DAY.isoformat()

    # 그 날짜에는 닫히고
    assert await _available_slot_ids(instructor_client, instructor_id, DAY) == [slot_b]
    # 같은 요일의 다른 날짜와 슬롯 설정은 그대로다
    assert await _available_slot_ids(instructor_client, instructor_id, NEXT_WEEK) == [slot_a, slot_b]
    slots = (await instructor_client.get("/calendars/me/time-slots")).json()
    assert all(s["is_active"] for s in slots)


@pytest.mark.asyncio
async def test_whole_day_block(instructor_client, instructor_id, my_calendar):
    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat()})
    assert r.status_code == 201, r.text
    assert r.json()[0]["time_slot_id"] is None

    res = await instructor_client.get(
        f"/calendars/{instructor_id}/availability",
        params={"start": DAY.isoformat(), "end": (DAY + timedelta(days=1)).isoformat()},
    )
    blocked_day, next_day = res.json()["days"]
    assert blocked_day["slots"] == [] and blocked_day["is_holiday"] is True
    assert len(next_day["slots"]) == 2


@pytest.mark.asyncio
async def test_delete_block_reopens_slot_and_duplicates_are_ignored(instructor_client, instructor_id, my_calendar):
    _, slot_a, _ = my_calendar
    body = {"date": DAY.isoformat(), "time_slot_ids": [slot_a]}
    first = (await instructor_client.post("/calendars/me/blocks", json=body)).json()
    again = (await instructor_client.post("/calendars/me/blocks", json=body)).json()
    assert [b["id"] for b in again] == [b["id"] for b in first]

    listed = await instructor_client.get(
        "/calendars/me/blocks", params={"start": DAY.isoformat(), "end": DAY.isoformat()}
    )
    assert [b["id"] for b in listed.json()] == [first[0]["id"]]

    assert (await instructor_client.delete(f"/calendars/me/blocks/{first[0]['id']}")).status_code == 204
    assert slot_a in await _available_slot_ids(instructor_client, instructor_id, DAY)
    assert (await instructor_client.delete(f"/calendars/me/blocks/{first[0]['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_block_validation(instructor_client, my_calendar, other_calendar):
    _, slot_a, _ = my_calendar
    _, _, others_slot, _ = other_calendar

    past = (date.today() - timedelta(days=1)).isoformat()
    assert (await instructor_client.post("/calendars/me/blocks", json={"date": past, "time_slot_ids": [slot_a]})).status_code == 400
    # 남의 캘린더 슬롯은 닫을 수 없다
    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat(), "time_slot_ids": [others_slot]})
    assert r.status_code == 404, r.text
    # 정의 안 된 필드
    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat(), "is_active": False})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_cannot_block_time_with_lesson_booking(
    instructor_client, my_calendar, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    _, slot_a, slot_b = my_calendar
    async with db_conn_and_sessionmaker() as session:
        guest = (await session.execute(text("select id from public.users where role = 'INSTRUCTOR' limit 1"))).scalar_one()
        await session.execute(
            text(
                """
                insert into public.bookings ("when", topic, type, status, time_slot_id, guest_id)
                values (:d, '레슨', 'LESSON', 'CONFIRMED', :slot, :guest)
                """
            ),
            {"d": DAY, "slot": slot_a, "guest": guest},
        )
        await session.commit()

    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat(), "time_slot_ids": [slot_a]})
    assert r.status_code == 409, r.text
    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat()})
    assert r.status_code == 409, r.text
    # 예약 없는 시간은 닫을 수 있다
    r = await instructor_client.post("/calendars/me/blocks", json={"date": DAY.isoformat(), "time_slot_ids": [slot_b]})
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_cannot_delete_others_block(
    instructor_client, other_calendar, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    _, calendar_id, slot, _ = other_calendar
    async with db_conn_and_sessionmaker() as session:
        block_id = (
            await session.execute(
                text(
                    """
                    insert into public.calendar_blocks (calendar_id, start_date, end_date, time_slot_id)
                    values (:c, :d, :d, :s) returning id
                    """
                ),
                {"c": calendar_id, "d": DAY, "s": slot},
            )
        ).scalar_one()
        await session.commit()
    await instructor_client.post("/calendars/me", json={"topics": ["x"], "description": "x"})
    assert (await instructor_client.delete(f"/calendars/me/blocks/{block_id}")).status_code == 404


# ── 고객 예약 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_customer_cannot_book_blocked_time(client, other_calendar, db_conn_and_sessionmaker):
    _, calendar_id, slot_a, slot_b = other_calendar
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                """
                insert into public.calendar_blocks (calendar_id, start_date, end_date, time_slot_id)
                values (:c, :d, :d, :s)
                """
            ),
            {"c": calendar_id, "d": DAY, "s": slot_a},
        )
        await session.commit()

    blocked = await client.post("/bookings", json={"time_slot_id": slot_a, "when": DAY.isoformat(), "topic": "레슨"})
    assert blocked.status_code == 400, blocked.text
    # 같은 날 다른 시간, 다른 날 같은 시간은 예약 가능
    assert (await client.post("/bookings", json={"time_slot_id": slot_b, "when": DAY.isoformat(), "topic": "레슨"})).status_code == 201
    assert (await client.post("/bookings", json={"time_slot_id": slot_a, "when": NEXT_WEEK.isoformat(), "topic": "레슨"})).status_code == 201


@pytest.mark.asyncio
async def test_customer_cannot_manage_blocks(client):
    params = {"start": DAY.isoformat(), "end": DAY.isoformat()}
    assert (await client.get("/calendars/me/blocks", params=params)).status_code == 403
    assert (await client.post("/calendars/me/blocks", json={"date": DAY.isoformat()})).status_code == 403


# ── 슬롯 전역 ON/OFF (의도된 전역 설정) ───────────────────────

@pytest.mark.asyncio
async def test_slot_deactivation_applies_to_every_date(instructor_client, instructor_id, my_calendar):
    _, slot_a, slot_b = my_calendar
    r = await instructor_client.patch(f"/calendars/me/time-slots/{slot_a}", json={"is_active": False})
    assert r.status_code == 200, r.text
    assert await _available_slot_ids(instructor_client, instructor_id, DAY) == [slot_b]
    assert await _available_slot_ids(instructor_client, instructor_id, NEXT_WEEK) == [slot_b]
