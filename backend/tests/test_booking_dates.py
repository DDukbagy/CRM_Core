"""예약 날짜 규칙 (docs/worklog/booking-date-rules.md 2절 명세 1~11)

날짜: TODAY(한국 날짜의 오늘)·YESTERDAY·TOMORROW. 서버도 한국 날짜로 "오늘"을 판단한다.

test_booking_flow.py 의 world 를 쓴다. 사용자: host(강사)·guest(담당 고객)·admin(관리자)
지난 날짜·오늘의 예약은 신청으로 만들 수 없으므로, _booking(...) 으로 원하는 날짜·상태의 예약을 바로 넣는다.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.clock import today_kst
from tests.conftest import insert_booking
from tests.test_booking_bulk_complete import BULK, _result, _status
from tests.test_booking_flow import _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _booking_count, _used

TODAY = today_kst()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


# ── 도우미 ────────────────────────────────────────────────────────

def _body(ids, day, slot: str = "slot_a", **extra) -> dict:
    """예약 신청 본문"""
    return {"time_slot_ids": [ids[slot]], "when": day.isoformat(), "topic": "레슨", **extra}


async def _booking(db, ids, day, status: str, *, slot: str = "slot_a", guest: str = "guest") -> tuple[int, int]:
    """그 날짜·상태의 예약을 API 를 거치지 않고 바로 만든다. (예약 id, 고정된 수강권 id) 를 돌려준다."""
    async with db() as s:
        cp = await _customer_pass(s, ids[guest], ids["host"], total=5)
        bid = await insert_booking(s, when=day, status=status, slot_id=ids[slot], guest_id=ids[guest], customer_pass_id=cp)
        await s.commit()
    return bid, cp


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 고객이 지난 날짜나 오늘 예약을 신청하려하면 → 400 을 반환하고 예약되지 않는다
@pytest.mark.parametrize("day", [YESTERDAY, TODAY], ids=["지난_날짜", "오늘"])
async def test_spec1_지난_날짜와_오늘은_신청할_수_없다(world, db_conn_and_sessionmaker, day):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        await _customer_pass(s, ids["guest"], ids["host"])  # 수강권은 있다 (거부 이유가 수강권이 아니라 날짜여야 한다)

    r = await act("guest").post("/bookings", json=_body(ids, day))

    assert r.status_code == 400, r.text
    assert await _booking_count(db, ids["guest"]) == 0, "거부된 신청은 예약을 남기지 않는다"


# 명세 2. 고객이 내일 이후의 예약을 신청하면 → 201 을 반환하고 예약된다
async def test_spec2_내일은_신청된다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        await _customer_pass(s, ids["guest"], ids["host"])

    r = await act("guest").post("/bookings", json=_body(ids, TOMORROW))

    assert r.status_code == 201, r.text
    assert await _booking_count(db, ids["guest"]) == 1


# 명세 3. 고객이 지난 날짜나 오늘의 신청 중인 예약을 철회하려하면 → 400 을 반환하고 신청 중 그대로 남는다
@pytest.mark.parametrize("day", [YESTERDAY, TODAY], ids=["지난_날짜", "오늘"])
async def test_spec3_지난_날짜와_오늘의_신청은_철회할_수_없다(world, db_conn_and_sessionmaker, day):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, _ = await _booking(db, ids, day, "REQUESTED")

    r = await act("guest").patch(f"/bookings/{bid}/withdraw")

    assert r.status_code == 400, r.text
    assert await _status(db, bid) == "REQUESTED"


# 명세 4. 고객이 지난 날짜나 오늘의 확정된 예약에 취소를 신청하려하면 → 400 을 반환하고 확정 그대로 남는다
@pytest.mark.parametrize("day", [YESTERDAY, TODAY], ids=["지난_날짜", "오늘"])
async def test_spec4_지난_날짜와_오늘의_예약은_취소_신청할_수_없다(world, db_conn_and_sessionmaker, day):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, _ = await _booking(db, ids, day, "CONFIRMED")

    r = await act("guest").patch(f"/bookings/{bid}/cancel")

    assert r.status_code == 400, r.text
    assert await _status(db, bid) == "CONFIRMED"


# 명세 5. 강사가 지난 날짜나 오늘의 신청을 확정하려하면 → 400 을 반환하고 신청 중 그대로 남는다
@pytest.mark.parametrize("day", [YESTERDAY, TODAY], ids=["지난_날짜", "오늘"])
async def test_spec5_지난_날짜와_오늘의_신청은_확정할_수_없다(world, db_conn_and_sessionmaker, day):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, _ = await _booking(db, ids, day, "REQUESTED")

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")

    assert r.status_code == 400, r.text
    assert await _status(db, bid) == "REQUESTED"


# 명세 6. 강사가 지난 날짜의 신청을 거절하면 → 200 을 반환하고 취소된다
async def test_spec6_지난_날짜의_신청도_거절할_수_있다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, _ = await _booking(db, ids, YESTERDAY, "REQUESTED")

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/decline")

    assert r.status_code == 200, r.text
    assert await _status(db, bid) == "CANCELLED"


# 명세 7. 강사가 지난 날짜의 확정된 예약을 취소하면 → 200 을 반환하고 취소되며 수강권은 차감되지 않는다
async def test_spec7_지난_날짜의_확정_예약도_강사는_취소할_수_있다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, cp = await _booking(db, ids, YESTERDAY, "CONFIRMED")

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/cancel")

    assert r.status_code == 200, r.text
    assert await _status(db, bid) == "CANCELLED"
    assert await _used(db, cp) == 0, "취소는 차감하지 않는다"


# 명세 8. 강사가 내일 이후의 확정된 예약을 완료하거나 노쇼 처리하려하면 → 409 를 반환하고 확정 그대로 남으며 수강권은 차감되지 않는다
@pytest.mark.parametrize("action", ["complete", "no-show"], ids=["완료", "노쇼"])
async def test_spec8_아직_오지_않은_수업은_완료_노쇼할_수_없다(world, db_conn_and_sessionmaker, action):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, cp = await _booking(db, ids, TOMORROW, "CONFIRMED")

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/{action}")

    assert r.status_code == 409, r.text
    assert await _status(db, bid) == "CONFIRMED"
    assert await _used(db, cp) == 0, "하지 않은 수업은 차감하지 않는다"


# 명세 9. 강사가 오늘이나 지난 날짜의 확정된 예약을 완료하면 → 200 을 반환하고 완료되며 수강권이 1회 차감된다
@pytest.mark.parametrize("day", [TODAY, YESTERDAY], ids=["오늘", "지난_날짜"])
async def test_spec9_수업_당일부터는_완료할_수_있다(world, db_conn_and_sessionmaker, day):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    bid, cp = await _booking(db, ids, day, "CONFIRMED")

    r = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")

    assert r.status_code == 200, r.text
    assert await _status(db, bid) == "COMPLETED"
    assert await _used(db, cp) == 1


# 명세 10. 일괄 완료 목록에 오늘 예약과 내일 예약이 섞여 있으면
#        → 200 을 반환하고 오늘 예약만 완료된다. 내일 예약은 결과에 실패와 이유가 담기고 확정 그대로 남는다
async def test_spec10_일괄_완료는_아직_오지_않은_수업만_남긴다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    today_bid, _ = await _booking(db, ids, TODAY, "CONFIRMED", slot="slot_a")
    tomorrow_bid, _ = await _booking(db, ids, TOMORROW, "CONFIRMED", slot="slot_b")

    r = await act("host").post(BULK, json={"booking_ids": [today_bid, tomorrow_bid]})

    assert r.status_code == 200, r.text
    assert await _status(db, today_bid) == "COMPLETED"
    assert await _status(db, tomorrow_bid) == "CONFIRMED"
    assert _result(r, tomorrow_bid)["ok"] is False
    assert _result(r, tomorrow_bid)["message"], "안 된 건에는 이유가 담긴다"


# 명세 11. 관리자가 고객 대신 지난 날짜에 예약을 신청하려하면 → 400 을 반환하고 예약되지 않는다
async def test_spec11_관리자도_지난_날짜에는_신청할_수_없다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        await _customer_pass(s, ids["admin"], ids["host"])  # 관리자 본인 이름으로 신청된다. 수강권은 있다

    r = await act("admin").post("/bookings", json=_body(ids, YESTERDAY))

    assert r.status_code == 400, r.text
    assert await _booking_count(db, ids["admin"]) == 0
