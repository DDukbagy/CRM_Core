"""예약 상태 전환 전체: 신청 → 확정 → 취소 신청/철회/승인/거절 → 완료·노쇼, 휴무·영업일 전환, 권한

한 테스트 안에서 강사·고객·다른 사용자를 오가야 하므로 로그인 사용자를 바꿔 끼울 수 있는 클라이언트를 쓴다.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import AsyncIterator, Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import deps as auth_deps
from app.core.auth.deps import CurrentUser
from app.db.session import get_session
from app.main import app

pytestmark = pytest.mark.asyncio

DAY = date.today() + timedelta(days=10)


async def _user(session: AsyncSession, role: str, manager_id: uuid.UUID | None = None) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role, manager_id, feedback_consent)
            values (:id, :u, :e, :d, true, 'ACTIVE', :r, :m, true)
            """
        ),
        {"id": str(uid), "u": f"bf-{uid.hex[:8]}", "e": f"bf-{uid.hex[:8]}@example.com", "d": f"{role.lower()}-{uid.hex[:4]}",
         "r": role, "m": str(manager_id) if manager_id else None},
    )
    return uid


@pytest_asyncio.fixture
async def world(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[tuple[Callable, dict]]:
    """강사(host)·담당 고객(guest)·다른 고객(stranger)·다른 강사(rival)·관리자(admin) + host 캘린더와 매일 슬롯 2개"""
    async with db_conn_and_sessionmaker() as session:
        host = await _user(session, "INSTRUCTOR")
        ids = {
            "host": host,
            "guest": await _user(session, "CUSTOMER", manager_id=host),
            "stranger": await _user(session, "CUSTOMER"),
            "rival": await _user(session, "INSTRUCTOR"),
            "admin": await _user(session, "ADMIN"),
        }
        cal = (await session.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[\"레슨\"]'::jsonb, '설명', :h) returning id"),
            {"h": str(host)},
        )).scalar_one()
        slots = []
        for start, end in (("09:00", "10:00"), ("10:00", "11:00")):
            slots.append((await session.execute(
                text(
                    f"""
                    insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)
                    values ('{start}'::time, '{end}'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id
                    """
                ),
                {"c": cal},
            )).scalar_one())
        await session.commit()
    ids["calendar"], ids["slot_a"], ids["slot_b"] = cal, slots[0], slots[1]

    roles = {"host": "INSTRUCTOR", "guest": "CUSTOMER", "stranger": "CUSTOMER", "rival": "INSTRUCTOR", "admin": "ADMIN"}
    current: dict = {}

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as s:
            yield s

    async def override_user() -> CurrentUser:
        return current["user"]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[auth_deps.get_current_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        def act(name: str) -> AsyncClient:
            current["user"] = CurrentUser(
                id=str(ids[name]), email=None, phone=None, username=name, display_name=name,
                role=roles[name], status="ACTIVE", is_active=True,
            )
            return ac
        yield act, ids
    app.dependency_overrides.clear()


async def _book(act, ids, slot="slot_a", day=DAY, **extra) -> dict:
    r = await act("guest").post("/bookings", json={"time_slot_id": ids[slot], "when": day.isoformat(), "topic": "레슨 신청", **extra})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "REQUESTED"
    return r.json()


async def _status(act, booking_id) -> str:
    return next(b for b in (await act("guest").get("/bookings/me")).json() if b["id"] == booking_id)["status"]


async def _available(act, ids, day=DAY) -> dict:
    r = await act("guest").get(f"/calendars/{ids['host']}/availability", params={"start": day.isoformat(), "end": day.isoformat()})
    return r.json()["days"][0]


# ── 레슨 예약 상태 전환 ───────────────────────────────────────

async def test_full_lesson_lifecycle(world):
    act, ids = world
    b = await _book(act, ids)
    bid = b["id"]

    # 신청 중에는 고객이 내용 수정 가능
    r = await act("guest").patch(f"/bookings/{bid}", json={"topic": "드라이버", "description": "슬라이스 교정"})
    assert r.status_code == 200 and r.json()["topic"] == "드라이버"

    # 신청한 시간은 가용 목록에서 빠진다
    assert ids["slot_a"] not in [s["time_slot_id"] for s in (await _available(act, ids))["slots"]]

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/confirm", json={"topic": "드라이버 교정"})
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED" and r.json()["topic"] == "드라이버 교정"
    assert (await act("guest").patch(f"/bookings/{bid}", json={"topic": "x"})).status_code == 400  # 확정 후 수정 불가

    # 취소 신청 → 고객이 철회 → 다시 신청 → 강사 거절 → 유지
    r = await act("guest").patch(f"/bookings/{bid}/cancel", json={"reason": "일정 변경"})
    assert r.status_code == 200 and r.json()["status"] == "CANCEL_REQUESTED"
    assert (await act("guest").patch(f"/bookings/{bid}/withdraw-cancel")).json()["status"] == "CONFIRMED"
    await act("guest").patch(f"/bookings/{bid}/cancel")
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/reject-cancel")).json()["status"] == "CONFIRMED"

    # 완료 (두 번 눌러도 그대로)
    r = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/complete")).json()["status"] == "COMPLETED"
    assert (await act("guest").patch(f"/bookings/{bid}/cancel")).status_code == 400   # 완료된 예약 취소 불가
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/cancel")).status_code == 400


async def test_cancel_request_approved(world):
    act, ids = world
    bid = (await _book(act, ids))["id"]
    await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")
    await act("guest").patch(f"/bookings/{bid}/cancel")
    r = await act("host").patch(f"/calendars/me/bookings/{bid}/approve-cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/approve-cancel")).status_code == 400
    # 취소된 시간은 다시 열린다
    assert ids["slot_a"] in [s["time_slot_id"] for s in (await _available(act, ids))["slots"]]


async def test_decline_and_withdraw_reopen_slot(world):
    act, ids = world
    first = (await _book(act, ids))["id"]
    r = await act("host").patch(f"/calendars/me/bookings/{first}/decline", json={"reason": "개인 사정"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["cancel_reason"] == "개인 사정"
    assert (await act("host").patch(f"/calendars/me/bookings/{first}/confirm")).status_code == 400  # 거절된 예약 확정 불가

    second = (await _book(act, ids))["id"]  # 같은 시간 다시 신청 가능
    assert (await act("guest").patch(f"/bookings/{second}/cancel")).status_code == 400  # 신청 중은 cancel 이 아니라 withdraw
    assert (await act("host").patch(f"/calendars/me/bookings/{second}/cancel")).status_code == 400  # 강사도 decline 으로
    r = await act("guest").patch(f"/bookings/{second}/withdraw", json={"reason": "다른 날로"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert (await act("host").patch(f"/calendars/me/bookings/{second}/decline")).json()["status"] == "CANCELLED"  # 이미 취소


async def test_host_cancel_and_no_show(world):
    act, ids = world
    a = (await _book(act, ids, slot="slot_a"))["id"]
    b = (await _book(act, ids, slot="slot_b"))["id"]
    for bid in (a, b):
        await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")

    r = await act("host").patch(f"/calendars/me/bookings/{a}/cancel", json={"reason": "우천"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"

    r = await act("host").patch(f"/calendars/me/bookings/{b}/no-show")
    assert r.status_code == 200 and r.json()["status"] == "NO_SHOW"
    assert (await act("host").patch(f"/calendars/me/bookings/{b}/no-show")).json()["status"] == "NO_SHOW"
    assert (await act("host").patch(f"/calendars/me/bookings/{b}/complete")).status_code == 400


async def test_duplicate_request_is_409(world):
    act, ids = world
    await _book(act, ids)
    r = await act("guest").post("/bookings", json={"time_slot_id": ids["slot_a"], "when": DAY.isoformat(), "topic": "x"})
    assert r.status_code == 409 and "SLOT_ALREADY_BOOKED" in r.text


# ── 권한 ──────────────────────────────────────────────────────

async def test_only_owner_can_change_booking(world):
    act, ids = world
    bid = (await _book(act, ids))["id"]

    assert (await act("rival").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 403
    assert (await act("rival").patch(f"/calendars/me/bookings/{bid}/decline")).status_code == 403
    assert (await act("stranger").patch(f"/bookings/{bid}/withdraw")).status_code == 403
    assert (await act("stranger").patch(f"/bookings/{bid}", json={"topic": "x"})).status_code == 403
    assert (await act("guest").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 403  # 고객은 강사 기능 불가
    # 관리자는 어느 캘린더든 처리 가능
    assert (await act("admin").patch(f"/calendars/me/bookings/{bid}/confirm")).json()["status"] == "CONFIRMED"
    assert (await act("stranger").patch(f"/bookings/{bid}/cancel")).status_code == 403
    assert (await act("guest").patch("/bookings/99999999/cancel")).status_code == 404


async def test_booking_type_permissions(world):
    act, ids = world
    body = {"time_slot_id": ids["slot_a"], "when": DAY.isoformat(), "topic": "x"}
    assert (await act("host").post("/bookings", json=body)).status_code == 403                        # 강사는 레슨 신청 불가
    # 예약은 레슨만. 휴무·영업일 전환은 /calendars/me/blocks
    for t in ("HOLIDAY", "WORK_OVERRIDE"):
        assert (await act("host").post("/bookings", json={**body, "type": t})).status_code == 400


async def test_ics_download_only_for_participants(world):
    act, ids = world
    bid = (await _book(act, ids))["id"]
    r = await act("guest").get(f"/bookings/{bid}/download")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in r.content
    assert (await act("host").get(f"/bookings/{bid}/download")).status_code == 200
    assert (await act("stranger").get(f"/bookings/{bid}/download")).status_code == 403
    assert (await act("rival").get(f"/bookings/{bid}/download")).status_code == 403


# ── 휴무 (사용자가 정한 5가지, 2026-10-01) ────────────────────
#   기본: 매일 07~20시 1시간 슬롯 / 정기 휴무일 / 임시 휴무일(하루 전체 닫기)
#   정기 휴무일 중 특정 날짜 열기 / 특정 날짜의 특정 시간대만 닫기(test_calendar.py)

async def _set_recurring_off(db, host_id, weekday: int):
    async with db() as session:
        await session.execute(
            text("update public.users set recurring_off_days = CAST(:d AS jsonb) where id = :h"),
            {"d": f"[{weekday}]", "h": str(host_id)},
        )
        await session.commit()


async def test_recurring_off_day(world, db_conn_and_sessionmaker):
    act, ids = world
    await _set_recurring_off(db_conn_and_sessionmaker, ids["host"], DAY.weekday())
    day = await _available(act, ids)
    assert day["slots"] == [] and day["off_type"] == "RECURRING" and day["is_holiday"] is False
    # 가용 목록에 없을 뿐 아니라 API 로 직접 신청해도 막힌다
    r = await act("guest").post("/bookings", json={"time_slot_id": ids["slot_a"], "when": DAY.isoformat(), "topic": "x"})
    assert r.status_code == 400 and "정기 휴무일" in r.text
    # 정기 휴무일 전체를 다시 '임시 휴무'로 닫을 수는 없다
    assert (await act("host").post("/calendars/me/blocks", json={"date": DAY.isoformat()})).status_code == 400


async def test_temporary_off_day(world):
    act, ids = world
    r = await act("host").post("/calendars/me/blocks", json={"date": DAY.isoformat(), "kind": "CLOSE", "reason": "개인 사정"})
    assert r.status_code == 201, r.text
    [block] = r.json()
    assert block["kind"] == "CLOSE" and block["time_slot_id"] is None

    day = await _available(act, ids)
    assert day["slots"] == [] and day["off_type"] == "TEMPORARY" and day["is_holiday"] is True
    r = await act("guest").post("/bookings", json={"time_slot_id": ids["slot_a"], "when": DAY.isoformat(), "topic": "x"})
    assert r.status_code == 400 and "임시 휴무일" in r.text

    assert (await act("host").delete(f"/calendars/me/blocks/{block['id']}")).status_code == 204   # 해제하면 다시 영업
    day = await _available(act, ids)
    assert day["off_type"] is None and len(day["slots"]) == 2


async def test_open_recurring_off_day(world, db_conn_and_sessionmaker):
    act, ids = world
    # 정기 휴무일이 아닌 날은 '열기'를 할 수 없다
    assert (await act("host").post("/calendars/me/blocks", json={"date": DAY.isoformat(), "kind": "OPEN"})).status_code == 400

    await _set_recurring_off(db_conn_and_sessionmaker, ids["host"], DAY.weekday())
    # 특정 시간만 열기
    r = await act("host").post("/calendars/me/blocks", json={"date": DAY.isoformat(), "kind": "OPEN", "time_slot_ids": [ids["slot_b"]]})
    assert r.status_code == 201, r.text
    day = await _available(act, ids)
    assert day["off_type"] is None and [s["time_slot_id"] for s in day["slots"]] == [ids["slot_b"]]
    # 다른 날짜(같은 요일)는 여전히 정기 휴무일
    nxt = await _available(act, ids, day=DAY + timedelta(days=7))
    assert nxt["off_type"] == "RECURRING"

    # 하루 전체 열기
    r = await act("host").post("/calendars/me/blocks", json={"date": DAY.isoformat(), "kind": "OPEN"})
    assert r.status_code == 201
    whole_open = r.json()[0]["id"]
    assert len((await _available(act, ids))["slots"]) == 2

    # 연 날에 레슨이 잡히면, 그 날을 다시 닫을(열기 해제) 수 없다
    await _book(act, ids, slot="slot_a")
    assert (await act("host").delete(f"/calendars/me/blocks/{whole_open}")).status_code == 409


async def test_default_calendar_on_instructor_approval(actor, db_conn_and_sessionmaker):
    from tests.conftest import insert_user

    act, people = actor
    async with db_conn_and_sessionmaker() as session:
        people["applicant"] = (await insert_user(session, "INSTRUCTOR", status="PENDING"), "INSTRUCTOR")
        people["boss"] = (await insert_user(session, "ADMIN"), "ADMIN")
    assert (await act("boss").post(f"/instructors/{people['applicant'][0]}/approve")).status_code == 200

    slots = (await act("applicant").get("/calendars/me/time-slots")).json()
    assert [(s["start_time"][:5], s["end_time"][:5]) for s in slots] == [(f"{h:02d}:00", f"{h + 1:02d}:00") for h in range(7, 20)]
    assert all(s["weekdays"] == [0, 1, 2, 3, 4, 5, 6] and s["is_active"] for s in slots)
    # 다시 승인해도 슬롯이 늘지 않는다
    await act("boss").post(f"/instructors/{people['applicant'][0]}/approve")
    assert len((await act("applicant").get("/calendars/me/time-slots")).json()) == 13


# ── 멤버십 연결 ───────────────────────────────────────────────

async def _membership(session: AsyncSession, customer, instructor, *, remaining=2, active=True, mtype="TIMES") -> str:
    mid = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.memberships (id, customer_id, instructor_id, type, total_count, remaining_count, started_at, expires_at, is_active)
            values (:id, :c, :i, :t, 10, :r, :s, :e, :a)
            """
        ),
        {"id": str(mid), "c": str(customer), "i": str(instructor), "t": mtype, "r": remaining,
         "s": date.today(), "e": date.today() - timedelta(days=1) if mtype == "PERIOD" else None, "a": active},
    )
    await session.commit()
    return str(mid)


async def test_membership_rules_and_deduction(world, db_conn_and_sessionmaker):
    act, ids = world
    async with db_conn_and_sessionmaker() as session:
        ok = await _membership(session, ids["guest"], ids["host"], remaining=1)
        empty = await _membership(session, ids["guest"], ids["host"], remaining=0)
        inactive = await _membership(session, ids["guest"], ids["host"], active=False)
        expired = await _membership(session, ids["guest"], ids["host"], mtype="PERIOD")
        others = await _membership(session, ids["stranger"], ids["host"])

    body = {"time_slot_id": ids["slot_b"], "when": DAY.isoformat(), "topic": "x"}
    assert (await act("guest").post("/bookings", json={**body, "membership_id": others})).status_code == 403
    for mid in (empty, inactive, expired):
        assert (await act("guest").post("/bookings", json={**body, "membership_id": mid})).status_code == 400
    assert (await act("guest").post("/bookings", json={**body, "membership_id": str(uuid.uuid4())})).status_code == 404

    bid = (await _book(act, ids, membership_id=ok))["id"]
    await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")
    await act("host").patch(f"/calendars/me/bookings/{bid}/complete")
    r = await act("guest").get(f"/memberships/{ok}")
    assert r.json()["remaining_count"] == 0 and r.json()["is_active"] is False


# ── 캘린더·슬롯 관리 ──────────────────────────────────────────

async def test_calendar_and_time_slot_management(world):
    act, ids = world
    host = act("host")
    assert (await host.post("/calendars/me", json={"topics": ["x"], "description": "x"})).status_code == 409
    r = await host.patch("/calendars/me", json={"description": "새 설명"})
    assert r.status_code == 200 and r.json()["description"] == "새 설명"
    assert (await host.get(f"/calendars/{uuid.uuid4()}")).status_code == 404

    assert (await host.post("/calendars/me/time-slots", json={"start_time": "12:00", "end_time": "11:00", "weekdays": [0]})).status_code == 400
    assert (await host.post("/calendars/me/time-slots", json={"start_time": "12:00", "end_time": "13:00", "weekdays": [7]})).status_code == 400
    r = await host.post("/calendars/me/time-slots", json={"start_time": "12:00", "end_time": "13:00", "weekdays": [0, 2]})
    assert r.status_code == 201
    new_slot = r.json()["id"]

    r = await host.patch(f"/calendars/me/time-slots/{new_slot}", json={"end_time": "14:00"})
    assert r.status_code == 200 and r.json()["end_time"].startswith("14:00")
    assert (await host.patch(f"/calendars/me/time-slots/{new_slot}", json={"end_time": "11:00"})).status_code == 400
    r = await host.patch(f"/calendars/me/time-slots/{new_slot}/weekdays", json={"weekdays": [1]})
    assert r.status_code == 200 and r.json()["weekdays"] == [1]
    assert (await act("rival").patch(f"/calendars/me/time-slots/{new_slot}/weekdays", json={"weekdays": [1]})).status_code == 403

    assert (await act("host").delete(f"/calendars/me/time-slots/{new_slot}")).status_code == 204
    await _book(act, ids)
    assert (await act("host").delete(f"/calendars/me/time-slots/{ids['slot_a']}")).status_code == 409  # 예약 있는 슬롯
    listed = (await act("guest").get(f"/calendars/{ids['host']}/time-slots")).json()
    assert {s["id"] for s in listed} == {ids["slot_a"], ids["slot_b"]}


async def test_host_booking_list_range(world):
    act, ids = world
    bid = (await _book(act, ids))["id"]
    r = await act("host").get("/calendars/me/bookings", params={"start": DAY.isoformat(), "end": DAY.isoformat()})
    assert [b["id"] for b in r.json()] == [bid]
    assert (await act("host").get("/calendars/me/bookings", params={"start": DAY.isoformat(), "end": (DAY - timedelta(days=1)).isoformat()})).status_code == 400
    assert (await act("rival").get("/calendars/me/bookings", params={"start": DAY.isoformat(), "end": DAY.isoformat()})).status_code == 404
