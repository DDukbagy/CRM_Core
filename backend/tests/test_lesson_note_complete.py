"""레슨노트 작성 = 레슨 완료 (docs/worklog/lesson-note-completes-booking.md 2절 명세 1~7)

노트 저장 요청
- POST /lesson-notes, json={"booking_id": 예약 id, "content": "글"}  → 이 파일에서는 NOTE 와 _note(예약 id) 를 쓴다
- 응답: 201 이면 저장된 노트(r.json()["booking_id"] 등), 거부되면 400·409

확인용 도우미 (모두 await 로 부른다)
- _status(db, 예약 id)       → 예약 상태 문자열. "CONFIRMED"(확정) · "COMPLETED"(완료) · "NO_SHOW" · "CANCELLED"
- _used(db, 수강권 id)        → 수강권 사용 횟수 (차감될 때마다 1씩 는다)
- _note_count(db, 예약 id)    → 그 예약에 연결된 노트 수 (0 또는 1)

준비
- 명세 1~5: test_booking_flow.py 의 world. 사용자: host(강사)·guest(담당 고객)
  예약은 _confirmed(...) 로 "확정" 상태까지 만든다. 수업 날짜는 DAY (오늘에서 10일 뒤)
  날짜 옮기기: clock.set(DAY) = 오늘이 수업 당일 / 옮기지 않으면 수업 10일 전
- 명세 6~7: test_concurrency.py 의 world (요청마다 별도 DB 연결) + gate (두 요청이 예약을 같이 읽은 뒤 진행하게 한다)
  요청을 보낼 때 headers=as_("host") 를 붙인다. 확인은 booking_status(real_db, 예약 id) · sessions_used(real_db, 수강권 id)
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests.test_booking_bulk_complete import _confirmed, _status
from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _used
from tests.test_concurrency import as_, book, booking_status, gate, give_pass, real_db, sessions_used  # noqa: F401  (gate·real_db 는 fixture)
from tests.test_concurrency import world as race_world  # noqa: F401  (명세 6·7 용 fixture)

pytestmark = pytest.mark.asyncio

NOTE = "/lesson-notes"


# ── 도우미 ────────────────────────────────────────────────────────

def _note(booking_id: int) -> dict:
    """노트 저장 요청 본문: 이 예약에 연결한 글 노트"""
    return {"booking_id": booking_id, "content": "백스윙 교정"}


async def _note_count(db, booking_id: int) -> int:
    """그 예약에 연결된 노트 수 (거부된 요청이 노트를 남기지 않았는지 확인용)"""
    async with db() as s:
        return (await s.execute(
            text("select count(*) from public.lesson_notes where booking_id = :b"), {"b": booking_id}
        )).scalar_one()


async def _use_up(db, cp: int) -> None:
    """수강권을 다 쓴 것으로 만든다 (남은 0회). 예약이 걸린 뒤에 생긴 상황을 흉내 낸다"""
    async with db() as s:
        await s.execute(text("update public.customer_passes set sessions_used = sessions_total where id = :i"), {"i": cp})
        await s.commit()


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 수업 당일인 내 확정 예약에 노트를 저장하면
#        → 201 을 반환하고 노트가 저장되며, 예약은 완료 상태가 되고 고정된 수강권이 1회 차감된다
async def test_spec1_확정_예약에_노트를_쓰면_완료되고_차감(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY)  # 오늘 = 수업 당일

    # host 가 이 예약(bid)에 노트를 저장하고, 응답 코드를 확인한다
    r = await act("host").post(NOTE, json=_note(bid))
    assert r.status_code == 201, r.text

    # 노트가 1개 저장됐는지 확인한다
    assert await _note_count(db, bid) == 1

    # 예약이 완료 상태가 됐는지 확인한다
    assert await _status(db, bid) == "COMPLETED"

    # 수강권이 1회 차감됐는지 확인한다
    assert await _used(db, cp) == 1


# 명세 2. 수업 날짜가 아직 오지 않은 확정 예약에 노트를 저장하면
#        → 409 로 거부되고 노트는 저장되지 않으며, 예약은 확정 그대로이고 수강권은 차감되지 않는다
async def test_spec2_수업_전_예약은_거부(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    # 날짜를 옮기지 않는다: 오늘은 수업 10일 전이다

    # host 가 이 예약에 노트를 저장하고, 응답 코드를 확인한다
    r = await act("host").post(NOTE, json=_note(bid))
    assert r.status_code == 409, r.text

    # 노트가 저장되지 않았는지 확인한다
    assert await _note_count(db, bid) == 0

    # 예약은 확정 그대로이고 수강권은 차감되지 않았는지 확인한다
    assert await _status(db, bid) == "CONFIRMED"
    assert await _used(db, cp) == 0


# 명세 3. 고정된 수강권을 다 쓴 확정 예약에 노트를 저장하면
#        → 409 로 거부되고 노트는 저장되지 않으며, 예약은 확정 그대로이고 사용 횟수도 그대로다
async def test_spec3_수강권을_다_썼으면_노트도_저장_안_됨(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=2)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    await _use_up(db, cp)  # 예약이 걸린 뒤 수강권이 다 쓴 상태가 됐다 (사용 2 / 총 2)
    clock.set(DAY)

    # host 가 이 예약에 노트를 저장하고, 응답 코드를 확인한다
    r = await act("host").post(NOTE, json=_note(bid))
    assert r.status_code == 409, r.text

    # 노트가 저장되지 않았는지 확인한다 (이 명세의 핵심: 완료가 거부되면 노트도 남지 않는다)
    assert await _note_count(db, bid) == 0

    # 예약은 확정 그대로이고, 사용 횟수는 2 그대로인지 확인한다
    assert await _status(db, bid) == "CONFIRMED"
    assert await _used(db, cp) == 2


# 명세 4. 이미 완료된 예약에 노트를 저장하면
#        → 201 을 반환하고 노트만 저장되며, 수강권은 더 차감되지 않는다
async def test_spec4_완료된_예약에는_노트만_저장(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY)
    # 강사가 대시보드에서 먼저 완료했다 (여기서 1회 차감)
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/complete")).status_code == 200

    # host 가 이 예약에 노트를 저장하고, 응답 코드를 확인한다
    r = await act("host").post(NOTE, json=_note(bid))
    assert r.status_code == 201, r.text

    # 노트가 1개 저장됐는지 확인한다
    assert await _note_count(db, bid) == 1

    # 예약은 완료 그대로이고, 수강권은 대시보드 완료 때의 1회에서 더 늘지 않았는지 확인한다
    assert await _status(db, bid) == "COMPLETED"
    assert await _used(db, cp) == 1


# 명세 5. 노쇼·취소된 예약에 노트를 저장하면
#        → 400 으로 거부되고 노트는 저장되지 않는다
@pytest.mark.parametrize("action, status_after", [("no-show", "NO_SHOW"), ("cancel", "CANCELLED")])
async def test_spec5_노쇼_취소된_예약은_거부(world, db_conn_and_sessionmaker, clock, action, status_after):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY)
    # 강사가 이 예약을 노쇼 또는 취소로 처리했다 (action 이 "no-show" 일 때와 "cancel" 일 때 한 번씩 실행된다)
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/{action}")).status_code == 200
    used_before = await _used(db, cp)  # 노쇼는 1회 차감, 취소는 0회

    # host 가 이 예약에 노트를 저장하고, 응답 코드를 확인한다
    r = await act("host").post(NOTE, json=_note(bid))
    assert r.status_code == 400, r.text

    # 노트가 저장되지 않았는지 확인한다
    assert await _note_count(db, bid) == 0

    # 예약 상태(status_after)와 사용 횟수(used_before)가 그대로인지 확인한다
    assert await _status(db, bid) == status_after
    assert await _used(db, cp) == used_before


# 명세 6. 같은 확정 예약에 노트 저장 요청 두 개가 동시에 오면
#        → 하나만 201 이고 다른 하나는 409 다. 노트는 1개만 남고 수강권은 1회만 차감된다
async def test_spec6_노트_저장을_동시에_두_번_보내도_한_번만_차감(real_db, race_world, gate, clock):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=5)
    bid = await book(w, 0, confirm=True)
    clock.after_lessons()  # 수업 날짜가 지난 뒤로 옮긴다

    gate.arm(2)  # 두 요청이 같은 예약을 모두 읽은 뒤 함께 다음으로 넘어간다 (저장 버튼을 두 번 누른 상황)

    # host 가 같은 노트 저장 요청을 동시에 두 번 보낸다
    responses = await asyncio.gather(
        c.post(NOTE, headers=as_("host"), json=_note(bid)),
        c.post(NOTE, headers=as_("host"), json=_note(bid)),
    )

    # 두 응답 코드가 201 하나, 409 하나인지 확인한다
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]

    # 노트는 1개만 남았는지 확인한다
    assert await _note_count(real_db, bid) == 1

    # 예약은 완료 상태이고 수강권은 1회만 차감됐는지 확인한다
    assert await booking_status(real_db, bid) == "COMPLETED"
    assert await sessions_used(real_db, cp) == 1


# 명세 7. 노트 저장과 대시보드의 완료 요청이 같은 예약에 동시에 오면
#        → 예약은 완료 상태가 되고 수강권은 1회만 차감된다. 노트 저장이 거부(409)됐다면 노트는 남지 않는다
async def test_spec7_노트_저장과_완료가_겹쳐도_한_번만_차감(real_db, race_world, gate, clock):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=5)
    bid = await book(w, 0, confirm=True)
    clock.after_lessons()

    gate.arm(2)  # 노트 저장과 완료 요청이 같은 예약을 모두 읽은 뒤 함께 다음으로 넘어간다

    # host 가 노트 저장과 완료 요청을 동시에 보낸다. 응답을 note_r, complete_r 로 받는다
    note_r, complete_r = await asyncio.gather(
        c.post(NOTE, headers=as_("host"), json=_note(bid)),
        c.patch(f"/calendars/me/bookings/{bid}/complete", headers=as_("host")),
    )
    assert note_r.status_code in (201, 409), note_r.text
    assert complete_r.status_code in (200, 409), complete_r.text

    # 예약이 완료 상태이고 수강권은 1회만 차감됐는지 확인한다 (누가 이겼든 같아야 한다)
    assert await booking_status(real_db, bid) == "COMPLETED"
    assert await sessions_used(real_db, cp) == 1

    # 노트 수가 노트 요청의 결과와 맞는지 확인한다: 201 이면 1개, 409 면 0개
    expected = 1 if note_r.status_code == 201 else 0
    assert await _note_count(real_db, bid) == expected
