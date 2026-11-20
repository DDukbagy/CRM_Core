"""예약 시 수강권 확인·고정 (docs/worklog/booking-pass-pinning.md 2절 명세 1~4)

test_booking_flow.py 의 world(강사 host·담당 고객 guest·다른 고객 stranger·다른 강사 rival + host 캘린더·슬롯 2개)를 그대로 쓴다.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)

pytestmark = pytest.mark.asyncio


async def _booking_count(db, guest) -> int:
    """그 고객의 예약 수 (거부된 요청이 예약을 남기지 않았는지 확인용)"""
    async with db() as s:
        return (await s.execute(text("select count(*) from public.bookings where guest_id = :g"), {"g": str(guest)})).scalar_one()


async def _used(db, cp_id: int) -> int:
    """수강권의 사용 횟수"""
    async with db() as s:
        return (await s.execute(text("select sessions_used from public.customer_passes where id = :i"), {"i": cp_id})).scalar_one()


def _body(ids, slot="slot_a", day=DAY, **extra) -> dict:
    return {"time_slot_ids": [ids[slot]], "when": day.isoformat(), "topic": "레슨 신청", **extra}


# 명세 1. 그 강사의 활성 수강권이 없는 고객이 예약하면 → 409 를 반환하고 예약은 생기지 않는다
async def test_spec1_그_강사_수강권_없으면_409_예약_없음(world, db_conn_and_sessionmaker):
    act, ids = world
    db = db_conn_and_sessionmaker
    # 다른 강사(rival)의 수강권은 있다: "수강권이 아예 없음"이 아니라 "이 강사의 수강권이 없음"을 확인한다
    async with db() as s:
        await _customer_pass(s, ids["guest"], ids["rival"])

    r = await act("guest").post("/bookings", json=_body(ids))

    # 응답 코드와, 예약이 남지 않았는지
    assert r.status_code == 409, r.text
    assert await _booking_count(db, ids["guest"]) == 0, "거부된 요청은 예약을 남기지 않는다"


# 명세 2. 다른 고객의 수강권이나 다른 강사의 수강권을 지정해 예약하면 → 400 을 반환하고 예약은 생기지 않는다
@pytest.mark.parametrize("whose", ["stranger_pass", "rival_pass"])
async def test_spec2_남의_수강권_지정하면_400_예약_없음(world, db_conn_and_sessionmaker, whose):
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        # 고객 본인의 이 강사 수강권도 있다: 거부 이유가 "수강권 없음"이 아니라 "지정한 수강권이 잘못됨"이어야 한다
        await _customer_pass(s, ids["guest"], ids["host"])
        if whose == "stranger_pass":
            wrong = await _customer_pass(s, ids["stranger"], ids["host"])  # 같은 강사, 다른 고객의 수강권
        else:
            wrong = await _customer_pass(s, ids["guest"], ids["rival"])  # 본인 것이지만 다른 강사의 수강권

    r = await act("guest").post("/bookings", json=_body(ids, customer_pass_id=wrong))

    # 응답 코드와, 예약이 남지 않았는지
    assert r.status_code == 400, r.text
    assert await _booking_count(db, ids["guest"]) == 0, "남의 수강권으로는 예약이 생기지 않는다"


# 명세 3. 잔여 1회 수강권에 진행 중 예약이 1건 있는데 그 수강권으로 또 예약하면 → 409 를 반환하고 예약은 생기지 않는다
#        (첫 예약을 취소하면 가능해진다)
async def test_spec3_잔여를_예약으로_다_쓰면_409_취소하면_가능(world, db_conn_and_sessionmaker):
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=1)

    first = await act("guest").post("/bookings", json=_body(ids, slot="slot_a", customer_pass_id=cp))
    assert first.status_code == 201, first.text

    second = await act("guest").post("/bookings", json=_body(ids, slot="slot_b", customer_pass_id=cp))

    # 두 번째 예약은 거부되고 예약은 첫 예약 1건 그대로
    assert second.status_code == 409, second.text
    assert await _booking_count(db, ids["guest"]) == 1, "잔여를 넘긴 예약은 생기지 않는다 (첫 예약 1건만)"

    # 첫 예약을 고객이 철회(신청 중 취소)한다
    w = await act("guest").patch(f"/bookings/{first.json()['id']}/withdraw")
    assert w.status_code == 200, w.text

    again = await act("guest").post("/bookings", json=_body(ids, slot="slot_b", customer_pass_id=cp))

    # 철회한 예약은 잔여에서 빠지므로 이제는 예약된다
    assert again.status_code == 201, again.text
    assert await _booking_count(db, ids["guest"]) == 2, "철회한 예약은 잔여에서 빠지므로 다시 예약된다 (취소 1 + 새 예약 1)"


# 명세 4. 같은 강사의 수강권이 2개일 때 나중 수강권을 지정해 예약하고 완료하면 → 지정한 수강권이 차감되어야 한다
async def test_spec4_지정한_수강권에서_차감(world, db_conn_and_sessionmaker):
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        older = await _customer_pass(s, ids["guest"], ids["host"])  # 먼저 발급 (지금 코드는 이것부터 차감한다)
        newer = await _customer_pass(s, ids["guest"], ids["host"])  # 나중 발급

    b = await act("guest").post("/bookings", json=_body(ids, customer_pass_id=newer))
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 200
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/complete")).status_code == 200

    # 지정한 수강권에서만 차감된다
    assert await _used(db, newer) == 1, "지정한 수강권에서 차감된다"
    assert await _used(db, older) == 0, "지정하지 않은 수강권은 그대로다"
