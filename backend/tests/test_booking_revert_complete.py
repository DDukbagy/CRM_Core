"""관리자의 완료 되돌리기 (docs/worklog/booking-revert-complete.md 2절 명세 1~7)

되돌리기 요청
- PATCH /admin/bookings/{예약 id}/revert-complete, json={"reason": "사유"} (사유는 선택)  → 이 파일에서는 _revert(...) 를 쓴다
- 응답(200): 예약 (status = "CANCELLED", cancel_reason 에 사유)
- 완료된 예약 목록: GET /admin/bookings/completed

준비
- 명세 1~4·6·7: test_booking_flow.py 의 world. 사용자: admin(관리자)·host(강사)·guest(담당 고객)
  예약을 확정까지 만든 뒤 clock.set(DAY) 로 수업 당일로 옮기고 host 가 완료한다 (_completed)
- 명세 5: test_concurrency.py 의 world + gate. 그 world 에는 관리자가 없어 host 의 역할을 관리자로 바꿔 쓴다
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.config import settings
from tests import test_concurrency
from tests.test_booking_bulk_complete import _confirmed, _status
from tests.test_booking_cleanup import CLEANUP, _holds_slot
from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _used
from tests.test_concurrency import as_, book, booking_status, gate, give_pass, real_db, sessions_used  # noqa: F401  (gate·real_db 는 fixture)
from tests.test_concurrency import world as race_world  # noqa: F401  (명세 5 용 fixture)

pytestmark = pytest.mark.asyncio

COMPLETED_LIST = "/admin/bookings/completed"


# ── 도우미 ────────────────────────────────────────────────────────

def _revert_url(booking_id: int) -> str:
    return f"/admin/bookings/{booking_id}/revert-complete"


async def _revert(act, who: str, booking_id: int, reason: str | None = "잘못 눌렀음"):
    return await act(who).patch(_revert_url(booking_id), json={"reason": reason} if reason else {})


async def _completed(act, ids, clock, cp: int, slot: str = "slot_a", day=DAY) -> int:
    """확정된 예약을 만들고 수업 당일로 옮겨 host 가 완료한다 (수강권 1회 차감). 예약 id 를 돌려준다"""
    bid = await _confirmed(act, ids, "guest", slot, day, cp)
    clock.set(day)
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/complete")).status_code == 200
    return bid


async def _pass_status(db, cp: int) -> str:
    async with db() as s:
        return (await s.execute(text("select status from public.customer_passes where id = :i"), {"i": cp})).scalar_one()


async def _pass(db, ids, total: int = 5) -> int:
    async with db() as s:
        return await _customer_pass(s, ids["guest"], ids["host"], total=total)


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 관리자가 완료된 예약을 되돌리면
#        → 200 을 반환하고 예약은 취소 상태가 되며 사유가 남는다. 수강권은 1회 복구되고, 그 시간은 다시 비어 있다
async def test_spec1_완료를_되돌리면_취소되고_1회_복구(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _completed(act, ids, clock, cp)
    assert await _used(db, cp) == 1

    r = await _revert(act, "admin", bid, "다른 예약을 잘못 완료함")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CANCELLED"
    assert "다른 예약을 잘못 완료함" in r.json()["cancel_reason"]
    assert await _status(db, bid) == "CANCELLED"
    assert await _used(db, cp) == 0
    assert await _holds_slot(db, bid) is False


# 명세 2. 그 완료로 수강권을 다 써서 '다 씀' 상태가 된 수강권이면
#        → 되돌린 뒤 수강권은 다시 사용 중(ACTIVE) 상태가 되고 남은 횟수가 1회 생긴다
async def test_spec2_다_쓴_수강권은_다시_사용_중으로(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids, total=1)
    bid = await _completed(act, ids, clock, cp)
    assert await _pass_status(db, cp) == "COMPLETED"

    r = await _revert(act, "admin", bid)
    assert r.status_code == 200, r.text
    assert await _pass_status(db, cp) == "ACTIVE"
    assert await _used(db, cp) == 0


# 명세 3. 완료 상태가 아닌 예약(확정·노쇼·취소)을 되돌리려 하면 → 409 로 거부되고 예약과 수강권은 그대로다
@pytest.mark.parametrize("action, status_now", [(None, "CONFIRMED"), ("no-show", "NO_SHOW"), ("cancel", "CANCELLED")])
async def test_spec3_완료가_아닌_예약은_거부(world, db_conn_and_sessionmaker, clock, action, status_now):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY)
    if action:
        assert (await act("host").patch(f"/calendars/me/bookings/{bid}/{action}")).status_code == 200
    used_before = await _used(db, cp)

    r = await _revert(act, "admin", bid)
    assert r.status_code == 409, r.text
    assert await _status(db, bid) == status_now
    assert await _used(db, cp) == used_before


# 명세 4. 관리자가 아닌 사람(그 예약의 강사, 고객)이 되돌리려 하면 → 403 으로 거부되고 예약은 완료 그대로다
@pytest.mark.parametrize("who", ["host", "guest"])
async def test_spec4_관리자만_되돌릴_수_있다(world, db_conn_and_sessionmaker, clock, who):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _completed(act, ids, clock, cp)

    r = await _revert(act, who, bid)
    assert r.status_code == 403, r.text
    assert await _status(db, bid) == "COMPLETED"
    assert await _used(db, cp) == 1


# 명세 5. 같은 예약의 되돌리기 요청 두 개가 동시에 오면 → 하나만 200 이고 다른 하나는 409 다. 수강권은 1회만 복구된다
async def test_spec5_동시에_두_번_되돌려도_한_번만_복구(real_db, race_world, gate, clock, monkeypatch):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=5)
    done, other = await book(w, 0, confirm=True), await book(w, 1, confirm=True)
    clock.after_lessons()
    for bid in (done, other):  # 2회 차감해 둔다: 복구가 두 번 되면 0 이 되어 드러난다
        assert (await c.patch(f"/calendars/me/bookings/{bid}/complete", headers=as_("host"))).status_code == 200
    assert await sessions_used(real_db, cp) == 2
    monkeypatch.setitem(test_concurrency.ROLES, "host", "ADMIN")  # 이 world 에는 관리자가 없다

    gate.arm(2)
    responses = await asyncio.gather(
        c.patch(_revert_url(done), headers=as_("host"), json={}),
        c.patch(_revert_url(done), headers=as_("host"), json={}),
    )
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert await booking_status(real_db, done) == "CANCELLED"
    assert await sessions_used(real_db, cp) == 1


# 명세 6. 완료된 예약 목록은 → 관리자에게만 보이고(강사는 403), 완료 상태인 예약만 강사·고객 이름과 함께 담긴다.
#        되돌린 예약은 목록에서 빠진다
async def test_spec6_완료된_예약_목록은_관리자만(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    done = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    waiting = await _confirmed(act, ids, "guest", "slot_b", DAY, cp)
    clock.set(DAY)
    assert (await act("host").patch(f"/calendars/me/bookings/{done}/complete")).status_code == 200

    assert (await act("host").get(COMPLETED_LIST)).status_code == 403
    r = await act("admin").get(COMPLETED_LIST)
    assert r.status_code == 200, r.text
    assert [b["id"] for b in r.json()] == [done]
    assert waiting not in [b["id"] for b in r.json()]
    row = r.json()[0]
    assert row["instructor_id"] == str(ids["host"])
    assert row["instructor_name"].startswith("instructor-") and row["guest_name"].startswith("customer-")

    assert (await _revert(act, "admin", done)).status_code == 200
    assert (await act("admin").get(COMPLETED_LIST)).json() == []


# 명세 7. 되돌린 예약은 수업일 + 3일이 지나 자동 정리가 돌아도 → 다시 완료되지 않고 수강권도 차감되지 않는다
async def test_spec7_되돌린_예약은_자동_정리가_다시_완료하지_않음(world, db_conn_and_sessionmaker, clock, monkeypatch):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    monkeypatch.setattr(settings, "CRON_SECRET", "s")
    cp = await _pass(db, ids)
    bid = await _completed(act, ids, clock, cp)
    assert (await _revert(act, "admin", bid)).status_code == 200
    clock.set(DAY + timedelta(days=4))

    r = await act("admin").post(CLEANUP, headers={"X-Cron-Secret": "s"})
    assert r.status_code == 200, r.text
    assert r.json()["completed"] == 0
    assert await _status(db, bid) == "CANCELLED"
    assert await _used(db, cp) == 0
