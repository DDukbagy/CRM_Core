"""지난 예약 자동 정리 (docs/worklog/booking-auto-cleanup.md 2절 명세 1~9)

자동 정리 요청
- POST /internal/bookings/cleanup, 헤더 X-Cron-Secret: 서버 설정 CRON_SECRET 과 같은 값  → 이 파일에서는 _cleanup(act) 를 쓴다
- 응답(200): {"completed": 완료한 건수, "cancelled": 취소한 건수, "left_confirmed": 차감하지 못해 확정으로 남긴 건수,
              "pending_cancel_requests": 수업일이 지난 '취소 신청 중' 건수(건드리지 않는다)}

준비
- test_booking_flow.py 의 world. 예약은 수업 날짜 DAY(오늘에서 10일 뒤)로 만들고, clock.set(...) 으로 오늘을 옮긴다
  DAY + 3 = 수업 후 3일째(아직 기다린다) / DAY + 4 = 3일이 지난 날(자동 완료)
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.config import settings
from tests.test_booking_bulk_complete import _confirmed, _status
from tests.test_booking_flow import DAY, _book, _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_booking_pass import _used
from tests.test_lesson_note_complete import _use_up

pytestmark = pytest.mark.asyncio

CLEANUP = "/internal/bookings/cleanup"
SECRET = "test-cron-secret"
DAY2 = DAY + timedelta(days=1)


# ── 도우미 ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cron_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """서버에 자동 정리용 비밀 값이 설정된 상태로 만든다 (명세 9 의 '설정되지 않음'만 따로 지운다)"""
    monkeypatch.setattr(settings, "CRON_SECRET", SECRET)


async def _cleanup(act, secret: str | None = SECRET):
    headers = {"X-Cron-Secret": secret} if secret is not None else {}
    return await act("host").post(CLEANUP, headers=headers)


async def _holds_slot(db, booking_id: int) -> bool:
    """그 예약이 아직 시간을 차지하고 있는지"""
    async with db() as s:
        return (await s.execute(
            text("select bool_or(holds_slot) from public.booking_slots where booking_id = :b"), {"b": booking_id}
        )).scalar_one()


async def _cancel_reason(db, booking_id: int) -> str | None:
    async with db() as s:
        return (await s.execute(text("select cancel_reason from public.bookings where id = :b"), {"b": booking_id})).scalar_one()


async def _pass(db, ids, total: int = 5) -> int:
    async with db() as s:
        return await _customer_pass(s, ids["guest"], ids["host"], total=total)


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 수업일 + 3일이 지난 확정 예약이 있을 때 자동 정리를 실행하면
#        → 200 을 반환하고 그 예약은 완료 상태가 되며 수강권이 1회 차감된다. 응답의 completed 는 1 이다
async def test_spec1_3일이_지난_확정_예약은_완료되고_차감(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY + timedelta(days=4))

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json()["completed"] == 1
    assert await _status(db, bid) == "COMPLETED"
    assert await _used(db, cp) == 1


# 명세 2. 수업 후 3일째인 확정 예약은 → 확정 그대로이고 차감되지 않는다 (강사가 처리할 시간을 3일 준다)
async def test_spec2_3일째인_확정_예약은_그대로(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY + timedelta(days=3))

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json()["completed"] == 0
    assert await _status(db, bid) == "CONFIRMED"
    assert await _used(db, cp) == 0


# 명세 3. 수업 날짜가 지난 신청(강사가 답하지 않음)은
#        → 취소되고 취소 사유가 남으며, 시간을 더 차지하지 않고 수강권은 차감되지 않는다. 응답의 cancelled 는 1 이다
async def test_spec3_수업_날짜가_지난_신청은_취소(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = (await _book(act, ids, customer_pass_id=cp))["id"]
    clock.set(DAY + timedelta(days=1))

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json()["cancelled"] == 1
    assert await _status(db, bid) == "CANCELLED"
    assert "자동" in (await _cancel_reason(db, bid) or "")
    assert await _holds_slot(db, bid) is False
    assert await _used(db, cp) == 0


# 명세 4. 수업 당일인 신청은 → 신청 중 그대로다 (취소는 수업 날짜가 지난 다음 날부터)
async def test_spec4_수업_당일의_신청은_그대로(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = (await _book(act, ids, customer_pass_id=cp))["id"]
    clock.set(DAY)

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json()["cancelled"] == 0
    assert await _status(db, bid) == "REQUESTED"
    assert await _holds_slot(db, bid) is True


# 명세 5. 수업일 + 3일이 지난 '취소 신청 중' 예약은
#        → 그대로 두고 차감하지 않는다. 응답의 pending_cancel_requests 에 1 로 잡힌다
async def test_spec5_취소_신청_중은_건드리지_않음(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    assert (await act("guest").patch(f"/bookings/{bid}/cancel", json={"reason": "일정 변경"})).status_code == 200
    clock.set(DAY + timedelta(days=4))

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json() == {"completed": 0, "cancelled": 0, "left_confirmed": 0, "pending_cancel_requests": 1}
    assert await _status(db, bid) == "CANCEL_REQUESTED"
    assert await _used(db, cp) == 0


# 명세 6. 3일이 지난 확정 예약 2건 중 1건의 수강권을 다 썼으면
#        → 차감할 수 있는 1건만 완료되고, 다른 1건은 확정 그대로 남는다. 응답은 completed 1, left_confirmed 1 이다
async def test_spec6_차감할_수_없는_건은_확정으로_남고_나머지는_완료(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    empty, ok = await _pass(db, ids, total=1), await _pass(db, ids, total=5)
    stuck = await _confirmed(act, ids, "guest", "slot_a", DAY, empty)
    fine = await _confirmed(act, ids, "guest", "slot_a", DAY2, ok)
    await _use_up(db, empty)
    clock.set(DAY2 + timedelta(days=4))

    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert (r.json()["completed"], r.json()["left_confirmed"]) == (1, 1)
    assert await _status(db, stuck) == "CONFIRMED"
    assert await _status(db, fine) == "COMPLETED"
    assert await _used(db, ok) == 1


# 명세 7. 자동 정리를 같은 날 두 번 실행하면 → 두 번째는 아무것도 처리하지 않고 수강권은 1회만 차감된 채다
async def test_spec7_두_번_실행해도_한_번만_차감(world, db_conn_and_sessionmaker, clock):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY + timedelta(days=4))

    assert (await _cleanup(act)).json()["completed"] == 1
    r = await _cleanup(act)
    assert r.status_code == 200, r.text
    assert r.json()["completed"] == 0
    assert await _used(db, cp) == 1


# 명세 8. 비밀 값이 틀리거나 없으면 → 401 로 거부되고 아무것도 바뀌지 않는다
@pytest.mark.parametrize("secret", ["wrong", None])
async def test_spec8_비밀_값이_틀리면_거부(world, db_conn_and_sessionmaker, clock, secret):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY + timedelta(days=4))

    r = await _cleanup(act, secret)
    assert r.status_code == 401, r.text
    assert await _status(db, bid) == "CONFIRMED"
    assert await _used(db, cp) == 0


# 명세 9. 서버에 비밀 값이 설정되지 않았으면 → 어떤 값을 보내도 404 다 (빈 값끼리 맞아서 열리는 일이 없다)
@pytest.mark.parametrize("secret", ["", SECRET, None])
async def test_spec9_서버에_설정이_없으면_닫혀_있음(world, db_conn_and_sessionmaker, clock, monkeypatch, secret):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    monkeypatch.setattr(settings, "CRON_SECRET", None)
    cp = await _pass(db, ids)
    bid = await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    clock.set(DAY + timedelta(days=4))

    r = await _cleanup(act, secret)
    assert r.status_code == 404, r.text
    assert await _status(db, bid) == "CONFIRMED"
