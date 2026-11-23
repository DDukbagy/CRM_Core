"""강사 앱 일괄 완료 (docs/worklog/booking-bulk-complete.md 2절 명세 1~7)

일괄 완료 요청
- POST /calendars/me/bookings/complete, json={"booking_ids": [예약 id, ...]}  → 이 파일에서는 BULK 와 _ids([...]) 를 쓴다
- 응답(200): {"results": [{"booking_id": 1, "ok": true, "message": null}, ...], "completed": 2, "failed": 1}
  한 건의 결과는 _result(r, 예약 id) 로 꺼낸다

준비
- 명세 1~6: test_booking_flow.py 의 world. 사용자: host(강사)·guest(담당 고객)·stranger(다른 고객)·rival(다른 강사)
  예약은 _confirmed(...) 로 "확정" 상태까지 만든다. 슬롯은 "slot_a"(09~10시)·"slot_b"(10~11시), 날짜는 DAY·DAY2(다음 날)
- 명세 7: test_concurrency.py 의 world (요청마다 별도 DB 연결) + gate (두 요청이 예약을 같이 읽은 뒤 진행하게 한다)
"""
from __future__ import annotations

import asyncio  # noqa: F401  (명세 7 에서 asyncio.gather 를 쓴다)
from datetime import timedelta

from sqlalchemy import text

from tests.conftest import insert_booking, insert_customer_pass
from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _used
from tests.test_concurrency import as_, book, booking_status, gate, give_pass, real_db, sessions_used  # noqa: F401  (gate·real_db 는 fixture)
from tests.test_concurrency import world as race_world  # noqa: F401  (명세 7 용 fixture)

DAY2 = DAY + timedelta(days=1)
BULK = "/calendars/me/bookings/complete"


# ── 도우미 ────────────────────────────────────────────────────────

def _ids(booking_ids: list[int]) -> dict:
    """일괄 완료 요청 본문"""
    return {"booking_ids": booking_ids}


def _result(r, booking_id: int) -> dict:
    """일괄 완료 응답에서 그 예약의 결과 한 건. 예) {"booking_id": 3, "ok": False, "message": "..."}"""
    return next(x for x in r.json()["results"] if x["booking_id"] == booking_id)


async def _status(db, booking_id: int) -> str:
    async with db() as s:
        return (await s.execute(text("select status from public.bookings where id = :i"), {"i": booking_id})).scalar_one()


async def _confirmed(act, ids, who: str, slot: str, day, cp: int) -> int:
    """who 가 그 날짜·슬롯을 수강권 cp 로 예약하고 host 가 확정한다. 예약 id 를 돌려준다."""
    r = await act(who).post("/bookings", json={"time_slot_ids": [ids[slot]], "when": day.isoformat(), "topic": "레슨", "customer_pass_id": cp})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")
    assert r.status_code == 200, r.text
    return bid


async def _rival_booking(db, ids) -> int:
    """다른 강사(rival)의 캘린더에 확정된 예약 1건을 만든다 (host 가 건드리면 안 되는 예약)"""
    async with db() as s:
        cal = (await s.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[]'::jsonb, '다른 강사', :h) returning id"),
            {"h": str(ids["rival"])},
        )).scalar_one()
        slot = (await s.execute(
            text("insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)"
                 " values ('09:00'::time, '10:00'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"),
            {"c": cal},
        )).scalar_one()
        cp = await insert_customer_pass(s, ids["stranger"], ids["rival"])
        bid = await insert_booking(s, when=DAY, status="CONFIRMED", slot_id=slot, guest_id=ids["stranger"], customer_pass_id=cp)
        await s.commit()
    return bid


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 확정된 예약 3건(고객 2명)을 한 번에 완료하면
#        → 200 을 반환하고 3건 모두 완료 상태가 되며, 2건을 예약한 고객의 수강권은 2회, 1건을 예약한 고객의 수강권은 1회 차감된다
async def test_spec1_세_건을_한_번에_완료(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp_guest = await _customer_pass(s, ids["guest"], ids["host"], total=5)
        cp_stranger = await _customer_pass(s, ids["stranger"], ids["host"], total=5)
    g1 = await _confirmed(act, ids, "guest", "slot_a", DAY, cp_guest)
    g2 = await _confirmed(act, ids, "guest", "slot_a", DAY2, cp_guest)
    s1 = await _confirmed(act, ids, "stranger", "slot_b", DAY, cp_stranger)

    # host 가 세 예약(g1, g2, s1)을 한 번에 완료 요청한다
    assert g1 != g2 != s1, "예약 번호가 서로 달라야 한다"
    assert len({g1, g2, s1}) == 3, "예약 번호가 서로 달라야 한다"
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([g1, g2, s1]))
    assert r.status_code == 200, r.text

    # 응답 코드를 확인한다
    assert r.status_code == 200, r.text

    # 세 예약이 모두 완료 상태인지 확인한다
    assert await _status(db, g1) == "COMPLETED"
    assert await _status(db, g2) == "COMPLETED"
    assert await _status(db, s1) == "COMPLETED"

    # 고객별 차감 횟수를 확인한다 (guest 2회, stranger 1회)
    assert await _used(db, cp_guest) == 2
    assert await _used(db, cp_stranger) == 1


# 명세 2. 3건 중 1건이 이미 취소된 예약이면
#        → 200 을 반환하고 나머지 2건은 완료·차감된다. 취소된 건은 결과에 실패와 이유가 담기고, 상태는 취소 그대로이며 차감되지 않는다
async def test_spec2_취소된_건만_실패하고_나머지는_완료(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp_guest = await _customer_pass(s, ids["guest"], ids["host"], total=5)
        cp_stranger = await _customer_pass(s, ids["stranger"], ids["host"], total=5)
    g1 = await _confirmed(act, ids, "guest", "slot_a", DAY, cp_guest)
    g2 = await _confirmed(act, ids, "guest", "slot_a", DAY2, cp_guest)
    s1 = await _confirmed(act, ids, "stranger", "slot_b", DAY, cp_stranger)
    # 강사가 목록을 열어 둔 사이 stranger 의 예약이 취소됐다
    assert (await act("host").patch(f"/calendars/me/bookings/{s1}/cancel")).status_code == 200

    # host 가 세 예약을 한 번에 완료 요청하고, 응답 코드를 확인한다
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([g1, g2, s1]))
    assert r.status_code == 200, r.text

    # guest 의 두 예약은 완료 상태이고 2회 차감됐는지 확인한다
    assert await _status(db, g1) == "COMPLETED"
    assert await _status(db, g2) == "COMPLETED"
    assert await _used(db, cp_guest) == 2

    # 취소된 예약(s1)의 결과가 실패이고 이유가 담겼는지 확인한다
    assert _result(r, s1)["ok"] is False
    assert _result(r, s1)["message"] != ""

    # 취소된 예약은 상태가 그대로(CANCELLED)이고 stranger 의 수강권은 차감되지 않았는지 확인한다
    assert await _status(db, s1) == "CANCELLED"
    assert await _used(db, cp_stranger) == 0


# 명세 3. 같은 고객의 예약 2건을 보냈는데 그 고객의 수강권이 1회만 남았으면
#        → 200 을 반환하고 날짜가 빠른 1건만 완료되어 1회 차감된다. 늦은 1건은 결과에 실패와 이유가 담기고 확정 상태 그대로다
async def test_spec3_수강권이_모자라면_빠른_날짜부터_완료(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=2)
    later = await _confirmed(act, ids, "guest", "slot_a", DAY2, cp)   # 늦은 날짜를 먼저 예약해 둔다 (예약 순서가 아니라 날짜 순서로 처리되는지 보기 위해)
    earlier = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    # 예약 2건이 걸린 뒤 강사가 수강권의 총 횟수를 1로 줄였다 (남은 1회에 확정 예약 2건)
    async with db() as s:
        await s.execute(text("update public.customer_passes set sessions_total = 1 where id = :i"), {"i": cp})
        await s.commit()

    # host 가 두 예약을 한 번에 완료 요청한다. 목록에는 늦은 날짜(later)를 앞에 넣는다
    assert later != earlier, "예약 번호가 서로 달라야 한다"

    # 응답 코드를 확인한다
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([later, earlier]))
    assert r.status_code == 200, r.text

    # 빠른 날짜(earlier)만 완료되고, 늦은 날짜(later)는 확정 상태 그대로인지 확인한다
    assert await _status(db, earlier) == "COMPLETED"
    assert await _status(db, later) == "CONFIRMED"

    # 늦은 날짜의 결과가 실패이고, 수강권은 1회만 차감됐는지 확인한다
    assert _result(r, later)["ok"] is False
    assert _result(r, later)["message"] != ""
    assert await _used(db, cp) == 1


# 명세 4. 목록에 다른 강사의 예약이 섞여 있으면
#        → 요청 전체가 404 로 거부되고, 내 예약도 완료되지 않으며 수강권은 차감되지 않는다
async def test_spec4_다른_강사의_예약이_섞이면_전체_404(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    mine = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    others = await _rival_booking(db, ids)

    # host 가 내 예약(mine)과 다른 강사의 예약(others)을 함께 완료 요청하고, 응답 코드를 확인한다
    assert mine != others, "예약 번호가 서로 달라야 한다"
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([mine, others]))
    assert r.status_code == 404, r.text

    # 내 예약도 다른 강사의 예약도 확정 상태 그대로이고, 내 고객의 수강권이 차감되지 않았는지 확인한다
    assert await _status(db, mine) == "CONFIRMED"
    assert await _status(db, others) == "CONFIRMED"
    assert await _used(db, cp) == 0

    # 잘못된 번호를 빼고 다시 보내면 완료된다 (앞 요청이 아무것도 건드리지 않았다는 확인이기도 하다)
    again = await act("host").post(BULK, json=_ids([mine]))
    assert again.status_code == 200, again.text
    assert await _status(db, mine) == "COMPLETED"


# 명세 5. 목록에 없는 예약 번호가 섞여 있으면
#        → 요청 전체가 404 로 거부되고, 내 예약도 완료되지 않으며 수강권은 차감되지 않는다
async def test_spec5_없는_번호가_섞이면_전체_404(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    mine = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    missing = 999_999_999  # 없는 예약 번호

    # host 가 내 예약(mine)과 없는 번호(missing)를 함께 완료 요청하고, 응답 코드를 확인한다
    assert mine != missing, "예약 번호가 서로 달라야 한다"
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([mine, missing]))
    assert r.status_code == 404, r.text

    # 내 예약이 확정 상태 그대로이고 수강권이 차감되지 않았는지 확인한다
    assert await _status(db, mine) == "CONFIRMED"
    assert await _used(db, cp) == 0

    # 잘못된 번호를 빼고 다시 보내면 완료된다
    again = await act("host").post(BULK, json=_ids([mine]))
    assert again.status_code == 200, again.text
    assert await _status(db, mine) == "COMPLETED"


# 명세 6. 같은 예약 번호를 두 번 넣어 보내면 → 200 을 반환하고 그 예약은 한 번만 완료되며 수강권은 1회만 차감된다
async def test_spec6_같은_번호를_두_번_넣어도_한_번만_완료(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    b = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)

    # host 가 같은 예약 번호를 두 번 넣어 완료 요청하고, 응답 코드를 확인한다
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    r = await act("host").post(BULK, json=_ids([b, b]))
    assert r.status_code == 200, r.text

    # 예약이 완료 상태이고, 수강권이 1회만 차감됐는지 확인한다
    assert await _status(db, b) == "COMPLETED"
    assert await _used(db, cp) == 1

    # 결과 목록에 그 예약이 한 번만 들어 있는지 확인한다
    assert len(r.json()["results"]) == 1


# 명세 7. 같은 일괄 완료 요청을 동시에 두 번 보내면
#        → 두 요청 모두 200 을 반환하고, 각 예약은 한 번만 완료되며 수강권은 예약 수만큼만 차감된다
async def test_spec7_같은_요청을_동시에_두_번_보내도_한_번씩만_차감(real_db, race_world, gate, clock):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=5)
    b1 = await book(w, 0, confirm=True)
    b2 = await book(w, 1, confirm=True)

    gate.arm(2)  # 두 요청이 같은 예약을 모두 읽은 뒤 함께 다음으로 넘어간다 (버튼을 두 번 누른 상황)

    # host 가 같은 일괄 완료 요청([b1, b2])을 동시에 두 번 보낸다

    # 두 요청의 응답 코드가 모두 200 인지 확인한다
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다 (완료·노쇼는 수업 당일부터 된다)
    responses = await asyncio.gather(
        c.post(BULK, headers=as_("host"), json=_ids([b1, b2])),
        c.post(BULK, headers=as_("host"), json=_ids([b1, b2])),
    )
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]

    # 두 예약이 모두 완료 상태인지 확인한다
    assert await booking_status(real_db, b1) == "COMPLETED"
    assert await booking_status(real_db, b2) == "COMPLETED"

    # 수강권이 예약 수(2회)만큼만 차감됐는지 확인한다
    assert await sessions_used(real_db, cp) == 2
