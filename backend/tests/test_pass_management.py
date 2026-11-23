"""수강권 관리: 걸린 예약과 동시 수정 (docs/worklog/pass-management-rules.md 2절 명세 1~6)

- 명세 1~3: test_booking_flow.py 의 world. _confirmed(...) 가 그 수강권에 걸린 확정 예약을 만든다
- 명세 4~6: test_concurrency.py 의 world (요청마다 별도 DB 연결) + 이 파일의 pass_gate.
  겹치는 순서를 매번 똑같이 만들기 위해 두 가지를 쓴다
  - pass_gate.arm(2): 수강권을 읽는 요청 2개가 모두 읽은 뒤 함께 저장하러 간다 (명세 5)
  - pass_gate.hold_write(): 수강권을 고치는 요청이 "읽은 뒤, 저장하기 전"에 멈춘다. 그 사이에 완료(차감)를 끝내고
    release() 로 풀어 주면, 고치는 요청은 차감 전의 값을 들고 저장하러 간다 (명세 4·6)
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests.test_booking_bulk_complete import DAY2, _confirmed
from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)
from tests.test_concurrency import as_, book, give_pass, real_db  # noqa: F401  (real_db 는 fixture)
from tests.test_concurrency import world as race_world  # noqa: F401  (명세 4~6 용 fixture)


# ── 준비 (fixture·도우미) ─────────────────────────────────────────

async def _pass(db, cp_id: int) -> dict:
    """수강권의 지금 값"""
    async with db() as s:
        row = (await s.execute(
            text("select sessions_total, sessions_used, status, note from public.customer_passes where id = :i"), {"i": cp_id}
        )).one()
    return {"sessions_total": row[0], "sessions_used": row[1], "status": row[2], "note": row[3]}


class PassGate:
    """수강권을 고치는 요청이 다른 요청과 겹치는 순서를 정해 주는 장치 (test_concurrency 의 RaceGate 와 같은 생각)"""

    def __init__(self) -> None:
        self.barrier: asyncio.Barrier | None = None
        self.holding = False
        self.read_done = asyncio.Event()   # 고치는 요청이 수강권을 읽었다
        self.go = asyncio.Event()          # 이제 저장해도 된다

    def arm(self, n: int) -> None:
        """수강권을 읽는 요청 n 개가 모두 읽을 때까지 서로 기다린다"""
        self.barrier = asyncio.Barrier(n)

    def hold_write(self) -> None:
        """다음에 오는 고치는 요청을 "읽은 뒤, 저장하기 전"에 멈춰 둔다"""
        self.holding = True

    async def wait_until_read(self) -> None:
        await asyncio.wait_for(self.read_done.wait(), timeout=5)

    def release(self) -> None:
        self.go.set()


@pytest.fixture
def pass_gate(monkeypatch) -> PassGate:
    """수강권 읽기(get_own_customer_pass)와 쓰기(add_sessions·update_customer_pass) 사이에 PassGate 를 끼운다."""
    from app.domains.passes.repository import PassRepository

    g = PassGate()
    read = PassRepository.get_own_customer_pass

    async def gated_read(self, *args, **kwargs):
        result = await read(self, *args, **kwargs)
        barrier = g.barrier
        if barrier is not None:
            await asyncio.wait_for(barrier.wait(), timeout=5)  # 다 모이지 않으면 5초 뒤 실패 (무한 대기 방지)
            g.barrier = None  # 한 번 모였으면 끝
        return result

    def held(original):
        async def wrapper(self, *args, **kwargs):
            if g.holding:
                g.holding = False  # 한 요청만 멈춘다
                g.read_done.set()
                await asyncio.wait_for(g.go.wait(), timeout=5)
            return await original(self, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(PassRepository, "get_own_customer_pass", gated_read)
    monkeypatch.setattr(PassRepository, "add_sessions", held(PassRepository.add_sessions))
    monkeypatch.setattr(PassRepository, "update_customer_pass", held(PassRepository.update_customer_pass))
    return g


# ── 테스트 ───────────────────────────────────────────────────────

# 명세 1. 예약이 걸려 있는 수강권을 취소나 만료로 바꾸려 하면
#        → 409 를 반환하고 수강권은 진행 중 그대로 남는다. 이유에 걸려 있는 예약 수가 담긴다
@pytest.mark.parametrize("new_status", ["CANCELLED", "EXPIRED"], ids=["취소", "만료"])
async def test_spec1_예약이_걸린_수강권은_취소_만료할_수_없다(world, db_conn_and_sessionmaker, new_status):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=5)
    await _confirmed(act, ids, "guest", "slot_a", DAY, cp)   # 이 수강권에 확정 예약 2건이 걸려 있다
    await _confirmed(act, ids, "guest", "slot_a", DAY2, cp)

    r = await act("host").patch(f"/passes/customer-passes/{cp}", json={"status": new_status})

    assert r.status_code == 409, r.text
    assert (await _pass(db, cp))["status"] == "ACTIVE"
    assert "2" in r.json()["error"]["message"], "걸려 있는 예약 수를 알려 준다"


# 명세 2. 남은 2회에 예약 2건이 걸려 있는 수강권의 사용 횟수를 1 올리려 하면 → 409 를 반환하고 사용 횟수는 그대로다
async def test_spec2_걸린_예약보다_남은_횟수가_적어지는_수정은_거부(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=2)  # 총 2회, 사용 0회
    await _confirmed(act, ids, "guest", "slot_a", DAY, cp)
    await _confirmed(act, ids, "guest", "slot_a", DAY2, cp)               # 남은 2회에 예약 2건

    r = await act("host").patch(f"/passes/customer-passes/{cp}", json={"sessions_used": 1})

    assert r.status_code == 409, r.text
    assert (await _pass(db, cp))["sessions_used"] == 0


# 명세 3. 예약이 걸려 있는 수강권에 횟수를 추가하거나 메모를 고치면 → 200 을 반환하고 그대로 반영된다
async def test_spec3_예약이_걸려_있어도_횟수_추가와_메모_수정은_된다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    db = db_conn_and_sessionmaker
    async with db() as s:
        cp = await _customer_pass(s, ids["guest"], ids["host"], total=2)
    await _confirmed(act, ids, "guest", "slot_a", DAY, cp)

    added = await act("host").post(f"/passes/customer-passes/{cp}/add-sessions", json={"sessions": 3})
    assert added.status_code == 200, added.text
    assert (await _pass(db, cp))["sessions_total"] == 5

    noted = await act("host").patch(f"/passes/customer-passes/{cp}", json={"note": "다음 달까지 사용"})
    assert noted.status_code == 200, noted.text
    assert (await _pass(db, cp))["note"] == "다음 달까지 사용"


# 명세 4. 남은 1회 수강권의 마지막 완료(차감)와 횟수 5회 추가가 동시에 오면
#        → 둘 다 200 을 반환하고, 총 횟수는 5 늘고 사용 횟수는 1 늘며 수강권은 진행 중이다
async def test_spec4_마지막_차감과_횟수_추가가_겹쳐도_둘_다_반영(real_db, race_world, pass_gate, clock):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=1)     # 총 1회 = 남은 1회
    bid = await book(w, 0, confirm=True)          # 그 수강권에 걸린 확정 예약
    clock.after_lessons()                          # 수업 날짜가 지난 뒤로 옮긴다 (완료는 수업 당일부터 된다)

    # 횟수 추가가 수강권을 읽고(남은 1회, 진행 중) 저장하기 전에 멈춘 사이, 마지막 완료가 차감을 끝낸다
    pass_gate.hold_write()
    adding = asyncio.create_task(
        c.post(f"/passes/customer-passes/{cp}/add-sessions", headers=as_("host"), json={"sessions": 5})
    )
    await pass_gate.wait_until_read()
    completed = await c.patch(f"/calendars/me/bookings/{bid}/complete", headers=as_("host"))
    pass_gate.release()
    added = await adding

    assert (completed.status_code, added.status_code) == (200, 200), (completed.text, added.text)
    after = await _pass(real_db, cp)
    assert (after["sessions_total"], after["sessions_used"]) == (6, 1)
    assert after["status"] == "ACTIVE", "5회가 남았는데 다 쓴 것으로 남으면 안 된다"


# 명세 5. 같은 수강권에 횟수 추가(3회, 5회)가 동시에 오면 → 둘 다 200 을 반환하고 총 횟수는 8 늘어난다
async def test_spec5_횟수_추가_두_번이_겹쳐도_둘_다_반영(real_db, race_world, pass_gate):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=2)

    pass_gate.arm(2)  # 두 추가 요청이 모두 수강권을 읽은 뒤 함께 저장하러 간다
    responses = await asyncio.gather(
        c.post(f"/passes/customer-passes/{cp}/add-sessions", headers=as_("host"), json={"sessions": 3}),
        c.post(f"/passes/customer-passes/{cp}/add-sessions", headers=as_("host"), json={"sessions": 5}),
    )

    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert (await _pass(real_db, cp))["sessions_total"] == 10, "2 + 3 + 5"


# 명세 6. 사용 횟수를 직접 바꾸는 수정과 완료(차감)가 동시에 오면
#        → 둘 다 200 을 반환하고, 결과는 두 요청을 차례로 처리한 것과 같다
#          (여기서는 완료 → 수정 순서로 겹치게 한다: 사용 횟수는 고친 값 2, 다 쓰지 않았으므로 진행 중)
async def test_spec6_수동_수정과_차감이_겹치면_차례로_처리한_결과(real_db, race_world, pass_gate, clock):  # noqa: F811
    w, c = race_world, race_world["client"]
    cp = await give_pass(real_db, w, total=5)     # 총 5회, 사용 0회
    bid = await book(w, 0, confirm=True)
    clock.after_lessons()

    # 수동 수정이 수강권을 읽고(사용 0회) 저장하기 전에 멈춘 사이, 완료가 차감을 끝낸다 (완료 → 수정 순서)
    pass_gate.hold_write()
    updating = asyncio.create_task(
        c.patch(f"/passes/customer-passes/{cp}", headers=as_("host"), json={"sessions_used": 2})
    )
    await pass_gate.wait_until_read()
    completed = await c.patch(f"/calendars/me/bookings/{bid}/complete", headers=as_("host"))
    pass_gate.release()
    updated = await updating

    assert (completed.status_code, updated.status_code) == (200, 200), (completed.text, updated.text)
    after = await _pass(real_db, cp)
    assert after["sessions_used"] == 2, "완료(1회) 뒤에 사용 횟수를 2 로 고친 결과"
    assert after["status"] == "ACTIVE", "다 쓰지 않았으면 진행 중이다"
