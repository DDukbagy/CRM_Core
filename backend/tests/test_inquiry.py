"""강사 문의하기(채팅방) → 고객이 담당 강사 지정"""
from __future__ import annotations

import pytest

from tests.conftest import insert_user

pytestmark = pytest.mark.asyncio


async def _people(db, people):
    async with db() as s:
        people["inst"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["pending"] = (await insert_user(s, "INSTRUCTOR", status="PENDING"), "INSTRUCTOR")
        people["cust"] = (await insert_user(s, "CUSTOMER"), "CUSTOMER")
        people["other"] = (await insert_user(s, "CUSTOMER"), "CUSTOMER")


async def test_inquiry_opens_one_room(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    inst = str(people["inst"][0])

    r = await act("cust").post("/chat/rooms", json={"instructor_id": inst})
    assert r.status_code == 200, r.text
    room = r.json()
    assert room["instructor_id"] == inst and room["other_id"] == inst and room["match_request_id"] is None
    # 다시 문의해도 같은 방
    assert (await act("cust").post("/chat/rooms", json={"instructor_id": inst})).json()["id"] == room["id"]
    # 강사 쪽 목록에도 보이고 메시지를 주고받을 수 있다
    assert [x["id"] for x in (await act("inst").get("/chat/rooms")).json()] == [room["id"]]
    assert (await act("cust").post(f"/chat/rooms/{room['id']}/messages", json={"content": "레슨 문의"})).status_code == 201


async def test_inquiry_rules(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    # 승인 안 된 강사·없는 강사·고객 대상은 404, 강사는 문의 불가 403
    assert (await act("cust").post("/chat/rooms", json={"instructor_id": str(people["pending"][0])})).status_code == 404
    assert (await act("cust").post("/chat/rooms", json={"instructor_id": str(people["other"][0])})).status_code == 404
    assert (await act("inst").post("/chat/rooms", json={"instructor_id": str(people["inst"][0])})).status_code == 403


async def test_customer_selects_manager_after_inquiry(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    inst = str(people["inst"][0])

    # 문의 전에는 지정할 수 없다
    r = await act("cust").put("/users/me/manager", json={"instructor_id": inst})
    assert r.status_code == 400 and "문의" in r.text

    await act("cust").post("/chat/rooms", json={"instructor_id": inst})
    r = await act("cust").put("/users/me/manager", json={"instructor_id": inst})
    assert r.status_code == 200 and r.json()["manager_id"] == inst
    # 강사의 담당 고객 목록에 나온다
    listed = (await act("inst").get("/users?role=CUSTOMER")).json()["items"]
    assert str(people["cust"][0]) in [u["id"] for u in listed]
    # 다른 고객은 이 방이 없으니 지정 불가, 강사는 이 API 를 쓸 수 없다
    assert (await act("other").put("/users/me/manager", json={"instructor_id": inst})).status_code == 400
    assert (await act("inst").put("/users/me/manager", json={"instructor_id": inst})).status_code == 403
