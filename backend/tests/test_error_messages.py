"""거부 응답의 이유: 화면에 그대로 보여 줄 수 있는 한국어 문장이어야 한다

두 앱과 웹은 오류 응답의 error.message 를 그대로 띄운다. 그래서 메시지가 영어이거나
자료 구조를 통째로 문자열로 바꾼 것이면 사용자가 이유를 알 수 없다.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.test_booking_flow import DAY, _customer_pass, world  # noqa: F401  (world 는 fixture)

HANGUL = re.compile(r"[가-힣]")
DOMAINS = Path(__file__).resolve().parents[1] / "app" / "domains"


def _body(ids, slot="slot_a") -> dict:
    return {"time_slot_ids": [ids[slot]], "when": DAY.isoformat(), "topic": "레슨"}


async def test_이미_예약된_시간은_코드와_문장을_따로_준다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    async with db_conn_and_sessionmaker() as s:
        await _customer_pass(s, ids["guest"], ids["host"])
        await _customer_pass(s, ids["stranger"], ids["host"])
    assert (await act("guest").post("/bookings", json=_body(ids))).status_code == 201

    r = await act("stranger").post("/bookings", json=_body(ids))

    assert r.status_code == 409, r.text
    error = r.json()["error"]
    assert error["code"] == "SLOT_ALREADY_BOOKED"
    assert HANGUL.search(error["message"]) and "{" not in error["message"], error["message"]
    # 화면이 다시 조회할 때 쓸 값은 details 로 따로 온다
    assert error["details"]["time_slot_ids"] == [ids["slot_a"]] and error["details"]["hint"] == "REFETCH_AVAILABILITY"


async def test_할_수_없는_상태_전환은_지금_상태를_한국어로_알려_준다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    async with db_conn_and_sessionmaker() as s:
        await _customer_pass(s, ids["guest"], ids["host"])
    bid = (await act("guest").post("/bookings", json=_body(ids))).json()["id"]

    # 확정하지 않은(신청 중) 예약을 완료 처리
    r = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")

    assert r.status_code == 409, r.text
    message = r.json()["error"]["message"]
    assert "신청 중" in message and "REQUESTED" not in message, message


async def test_남의_예약은_한국어로_거부한다(world, db_conn_and_sessionmaker):  # noqa: F811
    act, ids = world
    async with db_conn_and_sessionmaker() as s:
        await _customer_pass(s, ids["guest"], ids["host"])
    bid = (await act("guest").post("/bookings", json=_body(ids))).json()["id"]

    r = await act("stranger").patch(f"/bookings/{bid}/withdraw")

    assert r.status_code == 403, r.text
    assert HANGUL.search(r.json()["error"]["message"]), r.text


def test_도메인_코드의_거부_메시지는_모두_한국어다():
    """새 메시지를 영어로 추가하면 여기서 걸린다 (문자열로 직접 쓴 detail·_reject·_bad_request 만 본다)"""
    pattern = re.compile(r'(?:detail=|_reject\(|_bad_request\()f?"([^"]*)"')
    english = [
        f"{path.relative_to(DOMAINS)}:{n}: {m.group(1)}"
        for path in sorted(DOMAINS.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for m in pattern.finditer(line)
        if not HANGUL.search(m.group(1))
    ]
    assert english == [], "\n".join(english)
