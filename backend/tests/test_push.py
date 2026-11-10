"""푸시 알림: Expo Push API 발송(app/core/push.py), 토큰 등록 검증, 죽은 토큰 정리, 예약 상태 변경 시 알림

실제 Expo 서버에는 보내지 않는다. httpx 요청은 MockTransport 로, 예약 흐름에서는 send_push 를 바꿔 끼워 확인한다.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import push
from app.domains.users import repository as users_repository
from app.domains.users.repository import UserRepository
from tests.conftest import insert_user

pytestmark = pytest.mark.asyncio

TOKEN = "ExponentPushToken[abc123]"
_RealAsyncClient = httpx.AsyncClient


def _mock_expo(monkeypatch, handler) -> list[httpx.Request]:
    """app.core.push 가 만드는 httpx.AsyncClient 를 MockTransport 로 바꾼다. 받은 요청 목록을 돌려준다"""
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(push.httpx, "AsyncClient", factory)
    return seen


def _ok(_req: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"data": {"status": "ok", "id": "ticket-1"}})


def _not_registered(_req: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"data": {
        "status": "error", "message": "not a registered push token",
        "details": {"error": "DeviceNotRegistered"},
    }})


# 토큰 형식

@pytest.mark.parametrize("token, ok", [
    ("ExponentPushToken[abc]", True),
    ("ExpoPushToken[abc]", True),
    ("ExponentPushToken[abc", False),
    ("fcm-raw-token", False),
    ("", False),
    (None, False),
])
async def test_is_expo_push_token(token, ok):
    assert push.is_expo_push_token(token) is ok


# send_push (Expo Push API 호출)

async def test_send_push_posts_expo_message(monkeypatch):
    seen = _mock_expo(monkeypatch, _ok)
    assert await push.send_push(TOKEN, "제목", "본문", {"booking_id": 7}) is None

    assert len(seen) == 1
    req = seen[0]
    assert str(req.url) == push.EXPO_PUSH_URL and req.method == "POST"
    assert req.headers["accept"] == "application/json"
    body = json.loads(req.content)
    assert body == {
        "to": TOKEN, "title": "제목", "body": "본문", "data": {"booking_id": 7},
        "sound": "default", "priority": "high", "channelId": "default",
    }


async def test_send_push_skips_invalid_token(monkeypatch):
    seen = _mock_expo(monkeypatch, _ok)
    assert await push.send_push(None, "t", "b") is None
    assert await push.send_push("not-expo", "t", "b") is None
    assert seen == []


async def test_send_push_returns_ticket_error_code(monkeypatch):
    _mock_expo(monkeypatch, _not_registered)
    assert await push.send_push(TOKEN, "t", "b") == push.DEVICE_NOT_REGISTERED


async def test_send_push_ticket_list_format(monkeypatch):
    _mock_expo(monkeypatch, lambda r: httpx.Response(200, json={"data": [
        {"status": "error", "message": "x", "details": {"error": "MessageTooBig"}},
    ]}))
    assert await push.send_push(TOKEN, "t", "b") == "MessageTooBig"


async def test_send_push_http_error_does_not_raise(monkeypatch):
    _mock_expo(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    assert await push.send_push(TOKEN, "t", "b") == "http_error"


async def test_send_push_network_error_does_not_raise(monkeypatch):
    def fail(_req):
        raise httpx.ConnectError("down")
    _mock_expo(monkeypatch, fail)
    assert await push.send_push(TOKEN, "t", "b") == "network_error"


# 토큰 등록 API

async def _stored_token(sm: async_sessionmaker[AsyncSession], user_id) -> str | None:
    async with sm() as s:
        return (await s.execute(text("select push_token from public.users where id = :id"), {"id": str(user_id)})).scalar_one()


async def _me_id(client) -> str:
    return (await client.get("/users/me")).json()["id"]


async def test_put_push_token_stores_value(client, db_conn_and_sessionmaker):
    res = await client.put("/users/me/push-token", json={"token": "ExpoPushToken[new-format]"})
    assert res.status_code == 204, res.text
    assert await _stored_token(db_conn_and_sessionmaker, await _me_id(client)) == "ExpoPushToken[new-format]"

    assert (await client.delete("/users/me/push-token")).status_code == 204
    assert await _stored_token(db_conn_and_sessionmaker, await _me_id(client)) is None


@pytest.mark.parametrize("body", [
    {"token": "not-a-token"},
    {"token": "ExponentPushToken[" + "x" * 200 + "]"},
    "\"{\\\"token\\\": \\\"ExponentPushToken[abc]\\\"}\"",  # 이중 JSON 인코딩 (예전 앱 결함)
])
async def test_put_push_token_rejects_invalid(client, body):
    if isinstance(body, str):
        res = await client.put("/users/me/push-token", content=body, headers={"Content-Type": "application/json"})
    else:
        res = await client.put("/users/me/push-token", json=body)
    assert res.status_code == 422, res.text


# UserRepository.notify: 죽은 토큰 정리

async def test_notify_clears_token_when_device_not_registered(monkeypatch, db_conn_and_sessionmaker):
    _mock_expo(monkeypatch, _not_registered)
    async with db_conn_and_sessionmaker() as s:
        uid = await insert_user(s, "CUSTOMER", push_token=TOKEN)
        await UserRepository(s).notify(uid, "t", "b")
    assert await _stored_token(db_conn_and_sessionmaker, uid) is None


async def test_notify_keeps_token_on_success_and_other_errors(monkeypatch, db_conn_and_sessionmaker):
    async with db_conn_and_sessionmaker() as s:
        uid = await insert_user(s, "CUSTOMER", push_token=TOKEN)
        _mock_expo(monkeypatch, _ok)
        await UserRepository(s).notify(uid, "t", "b")
        _mock_expo(monkeypatch, lambda r: httpx.Response(500))
        await UserRepository(s).notify(uid, "t", "b")
    assert await _stored_token(db_conn_and_sessionmaker, uid) == TOKEN


async def test_notify_without_token_sends_nothing(monkeypatch, db_conn_and_sessionmaker):
    seen = _mock_expo(monkeypatch, _ok)
    async with db_conn_and_sessionmaker() as s:
        uid = await insert_user(s, "CUSTOMER")
        await UserRepository(s).notify(uid, "t", "b")
        await UserRepository(s).notify(None, "t", "b")
        await UserRepository(s).notify(uuid.uuid4(), "t", "b")  # 없는 사용자
    assert seen == []


# 예약 상태 변경 → 알림

async def test_booking_transitions_push_with_booking_id(monkeypatch, actor, db_conn_and_sessionmaker):
    act, people = actor
    sent: list[dict] = []

    async def fake_send_push(token, title, body, data=None):
        sent.append({"token": token, "title": title, "data": data})
        return None

    monkeypatch.setattr(users_repository, "send_push", fake_send_push)

    day = date.today() + timedelta(days=10)
    async with db_conn_and_sessionmaker() as s:
        host = await insert_user(s, "INSTRUCTOR", push_token="ExponentPushToken[host]")
        guest = await insert_user(s, "CUSTOMER", manager_id=host, push_token="ExponentPushToken[guest]")
        cal = (await s.execute(
            text("insert into public.calendars (topics, description, host_id) values ('[\"레슨\"]'::jsonb, '설명', :h) returning id"),
            {"h": str(host)},
        )).scalar_one()
        slot = (await s.execute(
            text(
                "insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id) "
                "values ('09:00'::time, '10:00'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"
            ),
            {"c": cal},
        )).scalar_one()
        await s.commit()
    people.update({"host": (host, "INSTRUCTOR"), "guest": (guest, "CUSTOMER")})

    r = await act("guest").post("/bookings", json={"time_slot_id": slot, "when": day.isoformat(), "topic": "레슨"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]

    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/confirm")).status_code == 200
    assert sent[-1] == {"token": "ExponentPushToken[guest]", "title": "예약 확정", "data": {"booking_id": bid}}

    # 고객의 취소 신청은 강사에게 간다
    assert (await act("guest").patch(f"/bookings/{bid}/cancel", json={"reason": "일정"})).status_code == 200
    assert sent[-1] == {"token": "ExponentPushToken[host]", "title": "취소 신청", "data": {"booking_id": bid}}

    assert (await act("host").patch(f"/calendars/me/bookings/{bid}/approve-cancel")).status_code == 200
    assert sent[-1]["title"] == "취소 승인" and sent[-1]["token"] == "ExponentPushToken[guest]"
