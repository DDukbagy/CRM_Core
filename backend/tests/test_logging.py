"""로깅: 요청 로그·요청 ID, 500 오류 로그, 인증 실패 원인, 사용 로그(예약 완료), 로그 형식(LOG_FORMAT)

worklog `docs/worklog/structured-logging.md` 2절 명세 1~7 을 하나씩 검증한다.

로그 확인은 pytest 의 caplog 로 한다.
- caplog.records: 남은 로그 한 줄씩(LogRecord). 로그의 칸(extra)은 속성으로 읽는다
    요청 로그 (로거 "app.request"): request_id, method, path, status, duration_ms, client
    사용 로그 (로거 "app.event")  : event, booking_id, actor_id, customer_pass_id (거부는 event 이름이 다르다)
- caplog.text: 남은 로그 전체. 무엇이 "없어야" 할 때 `not in` 으로 확인한다
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.logging import build_formatter
from app.main import app
from tests.test_auth import bearer, raw_client, supabase_token  # noqa: F401  (raw_client 는 fixture)
from tests.test_booking_flow import _book, _customer_pass, world  # noqa: F401  (world 는 fixture)

pytestmark = pytest.mark.asyncio

BOOM_PATH = "/__test__/boom"


@pytest_asyncio.fixture
async def boom_client() -> AsyncIterator[AsyncClient]:
    """처리하지 못한 예외를 던지는 임시 경로를 붙인 클라이언트. 테스트가 끝나면 경로를 뗀다.

    raise_app_exceptions=False: 서버 안의 예외를 테스트로 다시 던지지 않고, 실제 서버처럼 500 응답으로 받는다.
    """

    async def boom():
        raise RuntimeError("의도한 오류")

    app.add_api_route(BOOM_PATH, boom, methods=["GET"])
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != BOOM_PATH]


@pytest_asyncio.fixture
async def plain_client() -> AsyncIterator[AsyncClient]:
    """DB·인증이 필요 없는 경로(`/`)만 부르는 클라이언트"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def request_logs(caplog) -> list[logging.LogRecord]:
    return [rec for rec in caplog.records if rec.name == "app.request"]


def event_logs(caplog) -> list[logging.LogRecord]:
    return [rec for rec in caplog.records if rec.name == "app.event"]


# 명세 1: 정상 요청 → 응답 헤더에 X-Request-ID, 요청 로그 한 줄에 요청 ID·메서드·경로·상태·응답시간
async def test_request_log_has_fields(plain_client, caplog):
    with caplog.at_level(logging.INFO):
        r = await plain_client.get("/")
    assert r.status_code == 200, r.text

    logs = request_logs(caplog)
    assert len(logs) == 1
    rec = logs[0]

    # 응답 헤더에 X-Request-ID 가 있다
    assert "X-Request-ID" in r.headers
    # rec 의 request_id 가 응답 헤더의 X-Request-ID 와 같다
    assert rec.request_id == r.headers["X-Request-ID"]
    # rec 의 method · path · status 가 이 요청과 맞다 ("GET", "/", 200)
    assert rec.method == "GET"
    assert rec.path == "/"
    assert rec.status == 200
    # rec 의 duration_ms 가 있다 (None 이 아니다)
    assert rec.duration_ms is not None


# 명세 2: 처리 못 한 오류(500) → 응답 헤더에 X-Request-ID, 스택 트레이스는 1번
async def test_unhandled_error_has_request_id_and_one_stack(boom_client, caplog):
    with caplog.at_level(logging.INFO):
        r = await boom_client.get(BOOM_PATH)
    assert r.status_code == 500, r.text

    stacks = [rec for rec in caplog.records if rec.exc_info is not None]

    # 응답 헤더에 X-Request-ID 가 있다
    assert "X-Request-ID" in r.headers
    # 스택 트레이스가 붙은 로그(stacks)가 정확히 1개다
    assert len(stacks) == 1


# 명세 3: 받은 X-Request-ID 가 너무 길거나 줄바꿈이 섞여 있으면 → 버리고 새로 만든다
@pytest.mark.parametrize(
    "sent",
    [
        "a" * 500,              # 너무 긴 값
        "abc\nFAKE log line",   # 줄바꿈으로 가짜 로그 줄을 만들려는 값
    ],
    ids=["too-long", "newline"],
)
async def test_bad_request_id_is_replaced(plain_client, caplog, sent):
    with caplog.at_level(logging.INFO):
        r = await plain_client.get("/", headers={"X-Request-ID": sent})
    assert r.status_code == 200, r.text

    got = r.headers.get("X-Request-ID")

    # 응답의 X-Request-ID(got)가 있고, 보낸 값(sent)과 다르다
    assert got is not None
    assert got != sent
    # 로그 전체(caplog.text)에 보낸 값이 없다
    assert sent not in caplog.text


# 명세 4: Supabase 토큰 검증 실패 → 401, 로그에 실패 원인. 토큰은 로그에 없다
async def test_auth_failure_logs_reason_without_token(raw_client, caplog):
    # 서버와 다른 키로 서명한 토큰: Supabase 검증이 실패한다 (비상구 설정은 기본값 꺼짐)
    token = supabase_token("00000000-0000-0000-0000-000000000000", secret="wrong-secret-wrong-secret-wrong-secret")
    with caplog.at_level(logging.INFO):
        r = await raw_client.get("/auth/me", headers=bearer(token))
    assert r.status_code == 401, r.text

    auth_logs = [rec for rec in caplog.records if rec.name == "auth"]

    # auth_logs 중 하나의 메시지에 실패 원인("reason=")이 있다
    assert any("reason=" in rec.getMessage() for rec in auth_logs)
    # 로그 전체(caplog.text)에 토큰 문자열이 없다
    assert token not in caplog.text


# 명세 5: 예약 완료 성공 → 사용 로그에 예약 번호, 처리한 사람 ID, 차감된 수강권 번호
async def test_complete_writes_event_log(world, db_conn_and_sessionmaker, caplog):
    act, ids = world
    async with db_conn_and_sessionmaker() as session:
        cp_id = await _customer_pass(session, ids["guest"], ids["host"])
    bid = (await _book(act, ids))["id"]
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 200

    with caplog.at_level(logging.INFO):
        r = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")
    assert r.status_code == 200, r.text

    completed = [rec for rec in event_logs(caplog) if getattr(rec, "event", None) == "booking.completed"]
    assert len(completed) == 1
    rec = completed[0]

    # rec 의 booking_id 가 bid 와 같다
    assert rec.booking_id == bid
    # rec 의 actor_id 가 강사 ID 와 같다
    assert rec.actor_id == str(ids["host"])
    # rec 의 customer_pass_id 가 cp_id 와 같다
    assert rec.customer_pass_id == cp_id


# 명세 6: 예약 완료 거부(409) → 사용 로그가 남는다 (실제 완료와 구분되는 이름으로)
async def test_rejected_complete_writes_event_log(world, db_conn_and_sessionmaker, caplog):
    act, ids = world
    async with db_conn_and_sessionmaker() as session:
        cp_id = await _customer_pass(session, ids["guest"], ids["host"], total=1)
    bid = (await _book(act, ids))["id"]
    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 200

    # 예약에 고정된 수강권을 그사이 다 쓴 것으로 만들면 완료가 거부된다 (예약할 때는 수강권이 있어야 하므로)
    async with db_conn_and_sessionmaker() as session:
        await session.execute(text("update public.customer_passes set sessions_used = sessions_total where id = :i"), {"i": cp_id})
        await session.commit()
    with caplog.at_level(logging.INFO):
        r = await act("host").patch(f"/calendars/me/bookings/{bid}/complete")
    assert r.status_code == 409, r.text

    events = [getattr(rec, "event", None) for rec in event_logs(caplog)]

    # events 에 "booking.complete_rejected" 가 있다
    assert "booking.complete_rejected" in events
    # events 에 "booking.completed" 는 없다 (실제로 완료된 건과 섞이지 않는다)
    assert "booking.completed" not in events


# 명세 7: LOG_FORMAT=json → 로그 한 줄이 JSON 으로 읽힌다 / text → JSON 이 아닌 글자 형식
@pytest.mark.parametrize("fmt", ["json", "text"])
async def test_log_format(fmt):
    record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "request", None, None)
    record.request_id = "req-1"
    record.status = 200
    line = build_formatter(fmt).format(record)

    # json 이면 JSON 으로 읽히고 칸 값이 그대로, text 면 JSON 으로 읽히지 않는다
    if fmt == "json":
        data = json.loads(line)
        assert data["request_id"] == "req-1"
    else:
        with pytest.raises(json.JSONDecodeError):
            json.loads(line)
