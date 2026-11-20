"""수강권: 상품 관리, 고객 발급, 회차 사용·추가, 레슨 완료 시 자동 차감"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import _ensure_customer_managed_by, _ensure_instructor, insert_booking, insert_user

pytestmark = pytest.mark.asyncio

PASS_TYPE = {"name": "10회권", "duration_hours": 1, "session_count": 10, "price": 500000}


async def _create_type(ac, **overrides) -> dict:
    r = await ac.post("/passes/types", json={**PASS_TYPE, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


async def _assign(ac, customer_id, pass_type_id) -> dict:
    r = await ac.post("/passes/assign", json={"customer_id": str(customer_id), "pass_type_id": pass_type_id, "price_paid": 500000})
    assert r.status_code == 201, r.text
    return r.json()


async def _insert_pass_type(session: AsyncSession, instructor_id: uuid.UUID, *, is_active: bool = True) -> int:
    pass_type_id = (
        await session.execute(
            text(
                """
                insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, is_active)
                values (:i, '남의 상품', 1, 5, :a) returning id
                """
            ),
            {"i": str(instructor_id), "a": is_active},
        )
    ).scalar_one()
    await session.commit()
    return pass_type_id


# ── 상품 ──────────────────────────────────────────────────────

async def test_instructor_manages_pass_types(instructor_client):
    pt = await _create_type(instructor_client)
    assert pt["session_count"] == 10 and pt["is_active"] is True

    r = await instructor_client.patch(f"/passes/types/{pt['id']}", json={"price": 450000, "is_active": False})
    assert r.status_code == 200 and r.json()["price"] == 450000 and r.json()["is_active"] is False

    assert [p["id"] for p in (await instructor_client.get("/passes/types")).json()] == [pt["id"]]
    assert (await instructor_client.delete(f"/passes/types/{pt['id']}")).status_code == 204


@pytest.mark.parametrize(
    "overrides",
    [{"session_count": 0}, {"duration_hours": 0}, {"price": -1}, {"session_count": -3}],
)
async def test_invalid_pass_type_is_422(instructor_client, overrides):
    r = await instructor_client.post("/passes/types", json={**PASS_TYPE, **overrides})
    assert r.status_code == 422, r.text


async def test_customer_cannot_create_pass_type(client):
    assert (await client.post("/passes/types", json=PASS_TYPE)).status_code == 403


async def test_cannot_touch_others_pass_type(instructor_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    async with db_conn_and_sessionmaker() as session:
        others = await _insert_pass_type(session, await _ensure_instructor(session))
    assert (await instructor_client.patch(f"/passes/types/{others}", json={"price": 1})).status_code == 403
    assert (await instructor_client.delete(f"/passes/types/{others}")).status_code == 403
    assert (await instructor_client.patch("/passes/types/99999999", json={"price": 1})).status_code == 404


async def test_pass_type_with_active_customer_pass_cannot_be_deleted(instructor_client, managed_customer_id):
    pt = await _create_type(instructor_client)
    await _assign(instructor_client, managed_customer_id, pt["id"])
    assert (await instructor_client.delete(f"/passes/types/{pt['id']}")).status_code == 409


# ── 발급 ──────────────────────────────────────────────────────

async def test_assign_to_managed_customer(instructor_client, managed_customer_id):
    pt = await _create_type(instructor_client)
    cp = await _assign(instructor_client, managed_customer_id, pt["id"])
    assert cp["status"] == "ACTIVE"
    assert cp["sessions_total"] == 10 and cp["sessions_used"] == 0 and cp["sessions_remaining"] == 10
    assert cp["pass_name"] == "10회권" and cp["customer_name"]

    listed = (await instructor_client.get("/passes/customer-passes")).json()
    assert [p["id"] for p in listed] == [cp["id"]]


async def test_assign_rules(instructor_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession], managed_customer_id):
    pt = await _create_type(instructor_client)
    async with db_conn_and_sessionmaker() as session:
        other_instructor = await _ensure_instructor(session)
        unmanaged = await _ensure_customer_managed_by(session, other_instructor)
        others_type = await _insert_pass_type(session, other_instructor)

    body = {"customer_id": str(unmanaged), "pass_type_id": pt["id"]}
    assert (await instructor_client.post("/passes/assign", json=body)).status_code == 403          # 담당 아닌 고객
    body = {"customer_id": str(managed_customer_id), "pass_type_id": others_type}
    assert (await instructor_client.post("/passes/assign", json=body)).status_code == 403          # 남의 상품
    body = {"customer_id": str(uuid.uuid4()), "pass_type_id": pt["id"]}
    assert (await instructor_client.post("/passes/assign", json=body)).status_code == 404          # 없는 고객

    await instructor_client.patch(f"/passes/types/{pt['id']}", json={"is_active": False})
    body = {"customer_id": str(managed_customer_id), "pass_type_id": pt["id"]}
    assert (await instructor_client.post("/passes/assign", json=body)).status_code == 400          # 비활성 상품


# ── 회차 사용·추가 ────────────────────────────────────────────

async def test_using_all_sessions_completes_and_adding_reactivates(instructor_client, managed_customer_id):
    pt = await _create_type(instructor_client, session_count=2)
    cp = await _assign(instructor_client, managed_customer_id, pt["id"])

    r = await instructor_client.patch(f"/passes/customer-passes/{cp['id']}", json={"sessions_used": 2})
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED" and r.json()["sessions_remaining"] == 0

    r = await instructor_client.post(f"/passes/customer-passes/{cp['id']}/add-sessions", json={"sessions": 3, "note": "서비스"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ACTIVE"
    assert body["sessions_total"] == 5 and body["sessions_remaining"] == 3 and "서비스" in body["note"]

    assert (await instructor_client.post(f"/passes/customer-passes/{cp['id']}/add-sessions", json={"sessions": 0})).status_code == 400


async def test_sessions_used_cannot_exceed_total(instructor_client, managed_customer_id):
    cp = await _assign(instructor_client, managed_customer_id, (await _create_type(instructor_client, session_count=3))["id"])
    r = await instructor_client.patch(f"/passes/customer-passes/{cp['id']}", json={"sessions_used": 4})
    assert r.status_code == 400, r.text


@pytest.mark.parametrize("payload", [{"status": "UNKNOWN"}, {"sessions_used": -1}])
async def test_invalid_customer_pass_update_is_422(instructor_client, managed_customer_id, payload):
    cp = await _assign(instructor_client, managed_customer_id, (await _create_type(instructor_client))["id"])
    r = await instructor_client.patch(f"/passes/customer-passes/{cp['id']}", json=payload)
    assert r.status_code == 422, r.text


async def test_cancel_customer_pass(instructor_client, managed_customer_id):
    cp = await _assign(instructor_client, managed_customer_id, (await _create_type(instructor_client))["id"])
    r = await instructor_client.patch(f"/passes/customer-passes/{cp['id']}", json={"status": "CANCELLED"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


# ── 고객 조회 ─────────────────────────────────────────────────

async def test_customer_sees_only_own_passes(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        instructor = await _ensure_instructor(session)
        other_customer = await _ensure_customer_managed_by(session, instructor)
        pass_type = await _insert_pass_type(session, instructor)
        for customer in (me, other_customer):
            await session.execute(
                text(
                    """
                    insert into public.customer_passes
                      (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total, sessions_used, status)
                    values (:pt, :c, :i, '5회권', 1, 5, 1, 'ACTIVE')
                    """
                ),
                {"pt": pass_type, "c": str(customer), "i": str(instructor)},
            )
        await session.commit()

    r = await client.get("/passes/me")
    assert r.status_code == 200, r.text
    [mine] = r.json()
    assert mine["customer_id"] == str(me) and mine["sessions_remaining"] == 4
    assert mine["instructor"]["id"] == str(instructor) and mine["pass_type"]["id"] == pass_type
    assert (await client.get("/passes/customer-passes")).status_code == 403


# ── 레슨 완료 시 자동 차감 ────────────────────────────────────

async def test_completing_lesson_deducts_one_session(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    cp = await _assign(instructor_client, managed_customer_id, (await _create_type(instructor_client, session_count=1))["id"])
    lesson_day = date.today() + timedelta(days=3)
    async with db_conn_and_sessionmaker() as session:
        calendar_id = (
            await session.execute(
                text("insert into public.calendars (topics, description, host_id) values ('[]'::jsonb, 'c', :h) returning id"),
                {"h": str(instructor_id)},
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
        booking_id = await insert_booking(
            session, when=lesson_day, status="CONFIRMED", slot_id=slot_id, guest_id=managed_customer_id, customer_pass_id=cp["id"]
        )
        await session.commit()

    r = await instructor_client.patch(f"/calendars/me/bookings/{booking_id}/complete")
    assert r.status_code == 200, r.text
    after = next(p for p in (await instructor_client.get("/passes/customer-passes")).json() if p["id"] == cp["id"])
    assert after["sessions_used"] == 1 and after["status"] == "COMPLETED"

    # 이미 완료된 예약을 다시 완료해도 두 번 차감하지 않는다
    await instructor_client.patch(f"/calendars/me/bookings/{booking_id}/complete")
    again = next(p for p in (await instructor_client.get("/passes/customer-passes")).json() if p["id"] == cp["id"])
    assert again["sessions_used"] == 1


# ── 다른 강사의 예약·수강권 (변이 테스트로 찾은 빈틈) ──────────
# 명세: docs/worklog/test-mutation-check.md 2절
# 규칙(worklog 1절 표 B7·P4)을 망가뜨리면 실패한다. 응답과 함께 요청 뒤 DB 의 예약 상태·수강권 사용 횟수를 확인한다.

async def _confirmed_booking(session: AsyncSession, host_id: uuid.UUID, guest_id: uuid.UUID, customer_pass_id: int) -> int:
    """host 캘린더에 확정 예약 하나 (예약에 고정할 수강권 customer_pass_id)"""
    calendar_id = (
        await session.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[]'::jsonb, 'c', :h) returning id"),
            {"h": str(host_id)},
        )
    ).scalar_one()
    slot_id = (
        await session.execute(
            text(
                "insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)"
                " values ('09:00'::time, '10:00'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"
            ),
            {"c": calendar_id},
        )
    ).scalar_one()
    booking_id = await insert_booking(
        session, when=date.today() + timedelta(days=3), status="CONFIRMED", slot_id=slot_id, guest_id=guest_id,
        customer_pass_id=customer_pass_id,
    )
    await session.commit()
    return booking_id


async def _issue_pass(session: AsyncSession, instructor_id: uuid.UUID, customer_id: uuid.UUID) -> int:
    type_id = await _insert_pass_type(session, instructor_id)
    cp_id = (
        await session.execute(
            text(
                "insert into public.customer_passes (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total, sessions_used)"
                " values (:t, :c, :i, '10회권', 1, 10, 0) returning id"
            ),
            {"t": type_id, "c": str(customer_id), "i": str(instructor_id)},
        )
    ).scalar_one()
    await session.commit()
    return cp_id


async def _pass_state(session: AsyncSession, cp_id: int) -> tuple[int, str]:
    row = (await session.execute(text("select sessions_used, status from public.customer_passes where id = :i"), {"i": cp_id})).one()
    return row.sessions_used, row.status


async def _booking_status(session: AsyncSession, booking_id: int) -> str:
    return (await session.execute(text("select status from public.bookings where id = :i"), {"i": booking_id})).scalar_one()


# 명세 1: 확정된 예약을 다른 강사가 완료 처리하면 → 거부, 예약 상태와 고객 수강권은 그대로
async def test_other_instructor_cannot_complete_booking(actor, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    act, people = actor
    async with db_conn_and_sessionmaker() as s:
        people["owner"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")   # 예약을 받은 강사 (수강권 발급)
        people["other"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")   # 캘린더도 다르고 수강권도 발급하지 않은 강사
        people["cust"] = (await insert_user(s, "CUSTOMER", manager_id=people["owner"][0]), "CUSTOMER")
        cp_id = await _issue_pass(s, people["owner"][0], people["cust"][0])
        booking_id = await _confirmed_booking(s, people["owner"][0], people["cust"][0], cp_id)

    r = await act("other").patch(f"/calendars/me/bookings/{booking_id}/complete")

    async with db_conn_and_sessionmaker() as s:
        status_after = await _booking_status(s, booking_id)
        used_after, _ = await _pass_state(s, cp_id)

    assert r.status_code == 403, r.text
    assert status_after == "CONFIRMED"
    assert used_after == 0


# 명세 2: A 강사(먼저 발급)·B 강사(나중 발급) 수강권이 같이 있을 때 B 강사가 완료하면 → A 는 그대로, B 만 차감
async def test_completion_deducts_only_that_instructors_pass(actor, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    act, people = actor
    async with db_conn_and_sessionmaker() as s:
        people["a"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["b"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["cust"] = (await insert_user(s, "CUSTOMER", manager_id=people["b"][0]), "CUSTOMER")
        # 순서가 중요하다: A 를 먼저 발급해야, 강사 조건이 빠졌을 때 "먼저 발급된 것" 인 A 가 차감되어 빈틈이 드러난다
        a_pass = await _issue_pass(s, people["a"][0], people["cust"][0])
        b_pass = await _issue_pass(s, people["b"][0], people["cust"][0])
        booking_id = await _confirmed_booking(s, people["b"][0], people["cust"][0], b_pass)

    r = await act("b").patch(f"/calendars/me/bookings/{booking_id}/complete")
    assert r.status_code == 200, r.text

    async with db_conn_and_sessionmaker() as s:
        a_used, _ = await _pass_state(s, a_pass)
        b_used, _ = await _pass_state(s, b_pass)

    assert a_used == 0
    assert b_used == 1
