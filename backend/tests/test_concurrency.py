"""동시 요청: 예약 상태 전환과 수강권 차감

명세: docs/worklog/2026-11-13-pass-deduct-concurrency.md 2절

다른 테스트와 다른 점
- conftest 의 db_conn_and_sessionmaker 는 DB 연결 1개를 모든 요청이 같이 쓰고, 끝나면 롤백한다.
  연결이 1개면 쿼리가 줄을 서서 하나씩 실행되므로 동시 요청 문제가 재현되지 않는다.
- 여기서는 요청마다 커넥션 풀에서 **별도 연결**을 받고, 실제로 commit 한다.
  그래서 롤백으로 지워지지 않으므로 테스트가 끝나면 만든 데이터를 직접 지운다 (world fixture).
- RaceGate(gate fixture)로 요청들이 예약을 다 같이 읽은 뒤 진행하게 해서, 경쟁 상황을 매번 만든다.
- 로그인 사용자는 요청 헤더 X-Test-As 로 고른다. 강사와 고객 요청을 동시에 보내야 하기 때문이다.
  (test_booking_flow 의 act() 는 "지금 사용자" 하나를 바꿔 끼우는 방식이라 동시 요청에 쓸 수 없다)

빈칸: `# TODO(사용자)` 표시가 있는 줄을 채운다. `...` 자리에 코드를 쓴다.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import deps as auth_deps
from app.core.auth.deps import CurrentUser
from app.core.config import settings
from app.db.session import get_session
from app.main import app

import app.domains.calendar.router as calendar_router

pytestmark = pytest.mark.asyncio

DAY = date.today() + timedelta(days=10)
ROLES = {"host": "INSTRUCTOR", "guest": "CUSTOMER"}


# ── 준비 (fixture) ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def real_db() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """커넥션 풀이 있는 엔진. 세션마다 별도 연결을 받고, commit 하면 실제로 DB 에 남는다."""
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_size=10, max_overflow=0)
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def world(real_db: async_sessionmaker[AsyncSession]) -> AsyncIterator[dict]:
    """강사(host)·담당 고객(guest)·강사 캘린더·매일 열리는 시간 3개 + 요청용 클라이언트(client).
    끝나면 이 테스트가 만든 데이터를 지운다."""
    ids: dict = {}
    async with real_db() as s:
        for name, role in ROLES.items():
            uid = uuid.uuid4()
            await s.execute(
                text(
                    "insert into public.users (id, username, email, display_name, is_active, status, role, manager_id, feedback_consent)"
                    " values (:id, :u, :e, :d, true, 'ACTIVE', :r, :m, true)"
                ),
                {"id": str(uid), "u": f"cc-{uid.hex[:8]}", "e": f"cc-{uid.hex[:8]}@example.com", "d": name,
                 "r": role, "m": str(ids["host"]) if name == "guest" else None},
            )
            ids[name] = uid
        cal = (await s.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[\"레슨\"]'::jsonb, '동시성', :h) returning id"),
            {"h": str(ids["host"])},
        )).scalar_one()
        ids["slots"] = []
        for start, end in (("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00")):
            ids["slots"].append((await s.execute(
                text(
                    f"insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)"
                    f" values ('{start}'::time, '{end}'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"
                ),
                {"c": cal},
            )).scalar_one())
        await s.commit()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with real_db() as s:  # 요청마다 새 세션 = 풀에서 별도 연결
            yield s

    async def override_user(request: Request) -> CurrentUser:
        name = request.headers["X-Test-As"]
        return CurrentUser(
            id=str(ids[name]), email=None, phone=None, username=name, display_name=name,
            role=ROLES[name], status="ACTIVE", is_active=True,
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[auth_deps.get_current_user] = override_user
    app.dependency_overrides[calendar_router.get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ids["client"] = ac
            yield ids
    finally:
        app.dependency_overrides.clear()
        async with real_db() as s:
            # 수강권은 회원 삭제를 막으므로(RESTRICT) 먼저 지운다. 회원을 지우면 캘린더·시간·예약은 함께 지워진다
            p = {"h": str(ids["host"])}
            await s.execute(text("delete from public.customer_passes where instructor_id = :h"), p)
            await s.execute(text("delete from public.lesson_pass_types where instructor_id = :h"), p)
            await s.execute(text("delete from public.users where id in (:h, :g)"), {**p, "g": str(ids["guest"])})
            await s.commit()


class RaceGate:
    """동시 요청을 "확실히" 겹치게 만드는 장치.

    asyncio.gather 로 동시에 보내도, 앞 요청이 몇 ms 먼저 출발해 끝까지 처리되면 겹치지 않는다
    (실제로 이 장치 없이 돌리면 명세 2가 우연히 통과했다).
    arm(n) 을 부르면, 예약을 읽은 요청 n 개가 모두 읽을 때까지 서로 기다렸다가 함께 다음으로 넘어간다.
    → "둘 다 같은 상태를 읽은 뒤 각자 저장" 하는 경쟁 상황이 매번 만들어진다.
    """

    def __init__(self) -> None:
        self.barrier: asyncio.Barrier | None = None

    def arm(self, n: int) -> None:
        self.barrier = asyncio.Barrier(n)


@pytest.fixture
def gate(monkeypatch) -> RaceGate:
    """예약을 읽는 함수(BookingRepository.get_or_404) 뒤에 RaceGate 를 끼운다. 테스트가 끝나면 원래대로 돌아간다."""
    from app.domains.booking.repository import BookingRepository

    g = RaceGate()
    original = BookingRepository.get_or_404

    async def gated(self, booking_id: int):
        booking = await original(self, booking_id)
        if g.barrier is not None:
            await asyncio.wait_for(g.barrier.wait(), timeout=5)  # 다 모이지 않으면 5초 뒤 실패 (무한 대기 방지)
        return booking

    monkeypatch.setattr(BookingRepository, "get_or_404", gated)
    return g


# ── 도우미 ────────────────────────────────────────────────────────

async def give_pass(real_db, w, total: int) -> int:
    """고객에게 그 강사의 수강권(총 total 회)을 발급하고 id 를 돌려준다."""
    async with real_db() as s:
        type_id = (await s.execute(
            text("insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, is_active)"
                 " values (:i, '수강권', 1, :n, true) returning id"),
            {"i": str(w["host"]), "n": total},
        )).scalar_one()
        cp_id = (await s.execute(
            text("insert into public.customer_passes (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total)"
                 " values (:t, :c, :i, '수강권', 1, :n) returning id"),
            {"t": type_id, "c": str(w["guest"]), "i": str(w["host"]), "n": total},
        )).scalar_one()
        await s.commit()
    return cp_id


async def book(w, slot_index: int, *, confirm: bool) -> int:
    """고객이 slot_index 번째 시간에 예약 신청 (confirm=True 면 강사 확정까지). 예약 id 를 돌려준다."""
    c = w["client"]
    r = await c.post("/bookings", headers=as_("guest"),
                     json={"time_slot_id": w["slots"][slot_index], "when": DAY.isoformat(), "topic": "레슨"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    if confirm:
        r = await c.patch(f"/calendars/me/bookings/{bid}/confirm", headers=as_("host"))
        assert r.status_code == 200, r.text
    return bid


def as_(name: str) -> dict:
    """요청 헤더: 이 사용자로 로그인한 것처럼 보낸다. 예) c.patch(url, headers=as_("host"))"""
    return {"X-Test-As": name}


async def sessions_used(real_db, cp_id: int) -> int:
    async with real_db() as s:
        return (await s.execute(text("select sessions_used from public.customer_passes where id = :i"), {"i": cp_id})).scalar_one()


async def booking_status(real_db, booking_id: int) -> str:
    async with real_db() as s:
        return (await s.execute(text("select status from public.bookings where id = :i"), {"i": booking_id})).scalar_one()


# 강사 동작 URL: f"/calendars/me/bookings/{id}/confirm" · ".../complete" · ".../no-show"
# 고객 동작 URL: f"/bookings/{id}/withdraw"  (신청 철회)
# 모두 PATCH. 응답 코드는 r.status_code


# ── 테스트 ────────────────────────────────────────────────────────

async def test_spec4_같은_예약_완료_N번_동시_1회만_차감(real_db, world, gate):
    """명세 4: 같은 예약에 완료 요청 N번이 동시에 오면 → 수강권은 1회만 차감, 나머지는 409"""
    w, c = world, world["client"]
    cp_id = await give_pass(real_db, w, total=5)
    bid = await book(w, 0, confirm=True)
    url = f"/calendars/me/bookings/{bid}/complete"
    N = 3

    gate.arm(N)  # 이 뒤로 보내는 N개 요청은 예약을 다 같이 읽은 뒤 진행한다
    # TODO(사용자) 빈칸 1: 같은 완료 요청 N개를 "동시에" 보내고, 응답 N개를 responses 에 받는다
    #   힌트: 요청을 await 하나씩 하면 앞 요청이 끝나야 다음이 출발한다 (= 순서대로).
    #         동시에 출발시키려면 asyncio 의 함수 하나로 여러 요청을 한꺼번에 기다린다.
    #   힌트: 요청 하나는 c.patch(url, headers=as_("host"))
    responses = await asyncio.gather(*(c.patch(url, headers=as_("host")) for _ in range(N)))

    codes = sorted(r.status_code for r in responses)
    # TODO(사용자) 빈칸 2: 응답 코드가 "200 하나, 나머지 409" 인지 확인한다 (codes 는 정렬돼 있다)
    assert codes == [200, 409, 409], f"Expected [200, 409, 409], but got {codes}"
    # TODO(사용자) 빈칸 3: 수강권 사용 횟수가 정확히 1 인지 확인한다 (도우미 sessions_used 사용)
    assert await sessions_used(real_db, cp_id) == 1


async def test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감(real_db, world, gate):
    """명세 2: 한 고객의 서로 다른 예약 완료(노쇼 포함) 2건이 동시에 오면 → 수강권 2회 차감"""
    w, c = world, world["client"]
    # TODO(사용자) 빈칸 1: 2회를 차감해도 충분한 수강권을 발급한다 (give_pass)
    cp_id = await give_pass(real_db, w, total=2)
    b1 = await book(w, 0, confirm=True)
    b2 = await book(w, 1, confirm=True)

    gate.arm(2)
    # TODO(사용자) 빈칸 2: b1 은 완료, b2 는 노쇼 요청을 동시에 보낸다
    responses = await asyncio.gather(
        c.patch(f"/calendars/me/bookings/{b1}/complete", headers=as_("host")),
        c.patch(f"/calendars/me/bookings/{b2}/no-show", headers=as_("host")),
    )

    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    # TODO(사용자) 빈칸 3: 수강권이 2회 차감됐는지 확인한다
    assert await sessions_used(real_db, cp_id) == 2


async def test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만(real_db, world, gate):
    """명세 3: 잔여 1회 수강권으로 서로 다른 예약 2건(노쇼 포함)의 완료가 동시에 오면 → 1건만 완료·차감, 나머지 409"""
    w, c = world, world["client"]
    # TODO(사용자) 빈칸 1: 잔여 1회인 수강권을 발급한다
    cp_id = await give_pass(real_db, w, total=1)
    b1 = await book(w, 0, confirm=True)
    b2 = await book(w, 1, confirm=True)

    gate.arm(2)
    # TODO(사용자) 빈칸 2: b1 완료, b2 노쇼를 동시에 보낸다
    responses = await asyncio.gather(
        c.patch(f"/calendars/me/bookings/{b1}/complete", headers=as_("host")),
        c.patch(f"/calendars/me/bookings/{b2}/no-show", headers=as_("host")),
    )

    # TODO(사용자) 빈칸 3: 응답이 200 하나, 409 하나인지 확인한다
    assert [r.status_code for r in responses] == [200, 409] or [r.status_code for r in responses] == [409, 200]
    # TODO(사용자) 빈칸 4: 수강권 사용 횟수가 1 인지 확인한다 (총 횟수를 넘지 않는다)
    assert await sessions_used(real_db, cp_id) == 1
    # TODO(사용자) 빈칸 5: 409 를 받은 예약은 상태가 바뀌지 않았는지(CONFIRMED 그대로) 확인한다
    #   힌트: responses 순서는 보낸 순서와 같다. 어느 쪽이 409 인지 보고 그 예약의 booking_status 를 확인한다
    if responses[0].status_code == 409:
        assert await booking_status(real_db, b1) == "CONFIRMED"
    else:
        assert await booking_status(real_db, b2) == "CONFIRMED"


async def test_spec1_확정과_신청_철회_동시_하나만_성공(real_db, world, gate):
    """명세 1: 강사의 확정과 고객의 신청 철회가 동시에 오면 → 먼저 처리된 쪽만 성공, 나중 쪽은 409

    어느 쪽이 먼저 처리될지는 정할 수 없다. 그래서 "하나만 성공했는가"와 "최종 상태가 성공한 쪽 결과와 같은가"를 본다.
    """
    w, c = world, world["client"]
    bid = await book(w, 0, confirm=False)  # 신청 중(REQUESTED)

    gate.arm(2)
    # TODO(사용자) 빈칸 1: 강사 확정(host)과 고객 신청 철회(guest)를 동시에 보낸다
    confirm_r, withdraw_r = await asyncio.gather(
        c.patch(f"/calendars/me/bookings/{bid}/confirm", headers=as_("host")),
        c.patch(f"/bookings/{bid}/withdraw", headers=as_("guest")),
    )

    # TODO(사용자) 빈칸 2: 둘 중 정확히 하나만 200, 다른 하나는 409 인지 확인한다
    assert [confirm_r.status_code, withdraw_r.status_code].count(200) == 1
    assert [confirm_r.status_code, withdraw_r.status_code].count(409) == 1

    final = await booking_status(real_db, bid)
    # TODO(사용자) 빈칸 3: 확정이 성공했으면 최종 상태는 CONFIRMED, 철회가 성공했으면 CANCELLED 인지 확인한다
    if confirm_r.status_code == 200:
        assert final == "CONFIRMED"
    else:
        assert final == "CANCELLED"
