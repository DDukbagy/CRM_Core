"""예약 1건 = 레슨 1회, 여러 시간 예약 (docs/worklog/booking-lesson-hours.md 2절 명세 1~7)

- 명세 1~6: test_booking_flow.py 의 world 에 시간을 더한 `hours` fixture 를 쓴다.
  사용자: host(강사)·guest(담당 고객)·stranger(다른 고객)
  시간(슬롯 id): ids["s09"] 09~10시, ids["s10"] 10~11시, ids["s11"] 11~12시, ids["s12"] 12~13시, ids["s15"] 15~16시(떨어진 시간)
- 명세 7: test_concurrency.py 의 world (요청마다 별도 DB 연결) + 이 파일의 `create_gate`.
  사용자: host·guest·guest2, 시간: w["slots"][0] 09~10시, [1] 10~11시, [2] 11~12시
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import text

from tests.test_booking_flow import DAY, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _booking_count, _used
from tests.test_concurrency import as_, give_pass, real_db  # noqa: F401  (real_db 는 fixture)
from tests.test_concurrency import world as race_world  # noqa: F401  (명세 7 용 fixture)

pytestmark = pytest.mark.asyncio


# ── 준비 (fixture·도우미) ─────────────────────────────────────────

@pytest_asyncio.fixture
async def hours(world, db_conn_and_sessionmaker):  # noqa: F811
    """world 의 강사 캘린더에 시간을 더해 09~13시가 이어지게 하고, 떨어진 15~16시를 하나 둔다."""
    act, ids = world
    async with db_conn_and_sessionmaker() as s:
        for key, start, end in (("s11", "11:00", "12:00"), ("s12", "12:00", "13:00"), ("s15", "15:00", "16:00")):
            ids[key] = (await s.execute(
                text(
                    f"insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)"
                    f" values ('{start}'::time, '{end}'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"
                ),
                {"c": ids["calendar"]},
            )).scalar_one()
        await s.commit()
    ids["s09"], ids["s10"] = ids["slot_a"], ids["slot_b"]
    return act, ids


async def _pass(db, customer, instructor, *, hours: int = 2, total: int = 3) -> int:
    """고객에게 그 강사의 수강권(회당 hours 시간, 총 total 회)을 만들고 id 를 돌려준다."""
    async with db() as s:
        type_id = (await s.execute(
            text("insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, is_active)"
                 " values (:i, '수강권', :d, :n, true) returning id"),
            {"i": str(instructor), "d": hours, "n": total},
        )).scalar_one()
        cp_id = (await s.execute(
            text("insert into public.customer_passes (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total)"
                 " values (:t, :c, :i, '수강권', :d, :n) returning id"),
            {"t": type_id, "c": str(customer), "i": str(instructor), "d": hours, "n": total},
        )).scalar_one()
        await s.commit()
    return cp_id


def _body(slot_ids: list[int], **extra) -> dict:
    """예약 신청 본문. 예) _body([ids["s10"], ids["s11"]], customer_pass_id=cp)"""
    return {"time_slot_ids": slot_ids, "when": DAY.isoformat(), "topic": "레슨 신청", **extra}


class CreateGate:
    """동시에 온 예약 신청이 "둘 다 빈 시간임을 확인한 뒤" 함께 저장하러 가게 만드는 장치 (test_concurrency 의 RaceGate 와 같은 생각).

    이 장치가 없으면 한 요청이 끝까지 처리된 뒤 다음 요청이 시작돼, 겹치는 상황이 우연히 안 만들어질 수 있다.
    arm(n) 을 부르면 처음 n 개 요청이 확인을 마칠 때까지 서로 기다린다.
    """

    def __init__(self) -> None:
        self.barrier: asyncio.Barrier | None = None

    def arm(self, n: int) -> None:
        self.barrier = asyncio.Barrier(n)


@pytest.fixture
def create_gate(monkeypatch) -> CreateGate:
    """"그 시간에 이미 예약이 있는가" 확인(BookingRepository._active_exists) 뒤에 CreateGate 를 끼운다."""
    from app.domains.booking.repository import BookingRepository

    g = CreateGate()
    original = BookingRepository._active_exists

    async def gated(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        barrier = g.barrier
        if barrier is not None:
            await asyncio.wait_for(barrier.wait(), timeout=5)  # 다 모이지 않으면 5초 뒤 실패 (무한 대기 방지)
            g.barrier = None  # 한 번 모였으면 끝: 저장에 실패한 쪽이 다시 확인할 때는 기다리지 않는다
        return result

    monkeypatch.setattr(BookingRepository, "_active_exists", gated)
    return g


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 2시간 수강권으로 이어진 슬롯 2개를 예약하고 강사가 확정·완료하면
#        → 예약은 1건 생기고, 완료 처리하면 수강권은 1회만 차감된다
async def test_spec1_2시간_예약은_1건이고_완료하면_1회_차감(hours, db_conn_and_sessionmaker):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2, total=3)

    # guest 가 10~12시(슬롯 2개)를 수강권 cp 로 예약 신청한다
    r = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s11"]], customer_pass_id=cp))
    assert r.status_code == 201, r.text

    # 신청이 받아들여졌는지(응답 코드), 예약이 몇 건 생겼는지 확인한다
    assert await _booking_count(db, ids["guest"]) == 1

    # host 가 그 예약을 확정하고, 이어서 완료 처리한다 (둘 다 200 인지 확인)
    bid = r.json()["id"]
    confirmed = await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    complete = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")
    assert complete.status_code == 200, complete.text

    # 수강권이 몇 회 차감됐는지 확인한다
    assert await _used(db, cp) == 1


# 명세 2. 1회 남은 2시간 수강권으로 이어진 슬롯 2개를 예약하면 → 신청이 정상적으로 진행된다
async def test_spec2_1회_남은_2시간_수강권으로_2시간_예약(hours, db_conn_and_sessionmaker):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2, total=1)  # 총 1회 = 남은 1회

    # guest 가 이어진 슬롯 2개를 수강권 cp 로 예약 신청한다
    r = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s11"]], customer_pass_id=cp))
    assert r.status_code == 201, r.text

    # 응답 코드와 예약 건수를 확인한다
    assert await _booking_count(db, ids["guest"]) == 1


# 명세 3. 2시간 수강권인데 슬롯을 1개만(또는 3개) 보내면 → 400 을 반환하고 예약은 진행되지 않는다
#   같은 테스트가 두 번 돈다: keys 가 한 번은 ["s10"], 한 번은 ["s10", "s11", "s12"]
@pytest.mark.parametrize("keys", [["s10"], ["s10", "s11", "s12"]], ids=["슬롯_1개", "슬롯_3개"])
async def test_spec3_슬롯_수가_수강권_시간과_다르면_400(hours, db_conn_and_sessionmaker, keys):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2)
    slot_ids = [ids[k] for k in keys]  # 이번에 보낼 슬롯 id 목록 (1개 또는 3개)

    # guest 가 slot_ids 를 수강권 cp 로 예약 신청한다
    r = await act("guest").post("/bookings", json=_body(slot_ids, customer_pass_id=cp))
    # 응답 코드와, 예약이 생기지 않았는지 확인한다
    assert r.status_code == 400, r.text
    assert await _booking_count(db, ids["guest"]) == 0


# 명세 4. 2시간 수강권으로 이어지지 않은 슬롯 2개(예: 10시, 15시)를 보내면 → 400 을 반환하고 예약은 진행되지 않는다
async def test_spec4_이어지지_않은_슬롯이면_400(hours, db_conn_and_sessionmaker):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2)

    # guest 가 서로 떨어진 슬롯 2개를 수강권 cp 로 예약 신청한다
    r = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s15"]], customer_pass_id=cp))
    assert r.status_code == 400, r.text

    # 응답 코드와, 예약이 생기지 않았는지 확인한다
    assert await _booking_count(db, ids["guest"]) == 0


# 명세 5. 고른 슬롯 2개 중 하나가 이미 다른 고객의 예약이면 → 409 를 반환하고 예약은 진행되지 않는다
async def test_spec5_한_시간이_이미_예약돼_있으면_409_반쪽_예약_없음(hours, db_conn_and_sessionmaker):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2)
    # 다른 고객(stranger)이 1시간 수강권으로 11~12시를 먼저 예약해 둔다
    other = await _pass(db, ids["stranger"], ids["host"], hours=1)
    taken = await act("stranger").post("/bookings", json=_body([ids["s11"]], customer_pass_id=other))
    assert taken.status_code == 201, taken.text

    # guest 가 10~12시(11~12시가 이미 예약된 시간)를 수강권 cp 로 예약 신청한다
    r = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s11"]], customer_pass_id=cp))
    assert r.status_code == 409, r.text

    # 응답 코드와, guest 의 예약이 하나도 생기지 않았는지 확인한다 (10~11시만 반쪽으로 남으면 안 된다)
    assert await _booking_count(db, ids["guest"]) == 0


# 명세 6. 2시간 예약을 철회한 뒤 그 두 시간을 다시 예약하면 → 예약이 가능하다
async def test_spec6_철회하면_두_시간_모두_다시_예약된다(hours, db_conn_and_sessionmaker):
    act, ids = hours
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids["guest"], ids["host"], hours=2)
    first = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s11"]], customer_pass_id=cp))
    assert first.status_code == 201, first.text

    # guest 가 첫 예약을 철회한다 (200 인지 확인)
    bid = first.json()["id"]
    r = await act("guest").patch(f"/bookings/{bid}/withdraw")
    assert r.status_code == 200, r.text

    # 같은 두 시간을 다시 예약 신청하고, 응답 코드를 확인한다
    r2 = await act("guest").post("/bookings", json=_body([ids["s10"], ids["s11"]], customer_pass_id=cp))
    assert r2.status_code == 201, r2.text


# 명세 7. 두 고객이 한 시간이 겹치는 2시간 예약(09~11시, 10~12시)을 동시에 보내면
#        → 둘 중 하나만 201, 나머지는 409 이고 예약은 1건만 남는다
async def test_spec7_겹치는_2시간_예약_동시에_하나만_성공(real_db, race_world, create_gate):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp_a = await give_pass(real_db, w, total=3, customer="guest", hours=2)
    cp_b = await give_pass(real_db, w, total=3, customer="guest2", hours=2)
    slots = w["slots"]  # [0] 09~10시, [1] 10~11시, [2] 11~12시
    url = "/bookings"

    create_gate.arm(2)  # 두 요청이 모두 "빈 시간" 확인을 마친 뒤 함께 저장하러 간다

    # guest 는 09~11시를 cp_a 로, guest2 는 10~12시를 cp_b 로 동시에 신청한다
    responses = await asyncio.gather(
        c.post(url, headers=as_("guest"), json=_body([slots[0], slots[1]], customer_pass_id=cp_a)),
        c.post(url, headers=as_("guest2"), json=_body([slots[1], slots[2]], customer_pass_id=cp_b)),
    )

    # 201 이 정확히 하나, 409 가 정확히 하나인지 확인한다 (누가 이길지는 정할 수 없다)
    assert [r.status_code for r in responses].count(201) == 1
    assert [r.status_code for r in responses].count(409) == 1

    # 두 고객의 예약을 합쳐 1건만 남았는지 확인한다
    assert await _booking_count(real_db, w["guest"]) + await _booking_count(real_db, w["guest2"]) == 1
