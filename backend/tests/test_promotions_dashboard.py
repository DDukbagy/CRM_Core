"""강사 프로모션(웹 관리·고객 표시)과 매출 대시보드"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import insert_user

pytestmark = pytest.mark.asyncio
TODAY = date.today()


async def _setup(db, people):
    async with db() as s:
        people["inst"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["rival"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["cust"] = (await insert_user(s, "CUSTOMER", manager_id=people["inst"][0]), "CUSTOMER")
        type_id = (await s.execute(
            text("insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, price, is_active)"
                 " values (:i, '10회권', 1, 10, 500000, true) returning id"), {"i": str(people["inst"][0])})).scalar_one()
        await s.commit()
    return type_id


async def test_promotion_crud_and_customer_view(actor, db_conn_and_sessionmaker):
    act, people = actor
    type_id = await _setup(db_conn_and_sessionmaker, people)
    body = {"title": "가을 할인", "pass_type_id": type_id, "discount_type": "PERCENT", "discount_value": 10,
            "start_date": str(TODAY), "end_date": str(TODAY + timedelta(days=30))}
    r = await act("inst").post("/promotions", json=body)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "ONGOING" and p["pass_type_name"] == "10회권" and p["discounted_price"] == 450000

    # 예정된 것·중지한 것은 고객에게 안 보인다
    await act("inst").post("/promotions", json={**body, "title": "겨울", "start_date": str(TODAY + timedelta(days=40)), "end_date": str(TODAY + timedelta(days=50))})
    seen = (await act("cust").get(f"/promotions/instructor/{people['inst'][0]}")).json()
    assert [x["title"] for x in seen] == ["가을 할인"]
    assert (await act("inst").patch(f"/promotions/{p['id']}", json={"is_active": False})).json()["status"] == "PAUSED"
    assert (await act("cust").get(f"/promotions/instructor/{people['inst'][0]}")).json() == []
    assert len((await act("inst").get("/promotions/me")).json()) == 2

    # 남의 프로모션·남의 수강권·고객 작성 불가, 잘못된 할인
    assert (await act("rival").patch(f"/promotions/{p['id']}", json={"title": "x"})).status_code == 404
    assert (await act("rival").post("/promotions", json=body)).status_code == 404
    assert (await act("cust").post("/promotions", json=body)).status_code == 403
    assert (await act("inst").post("/promotions", json={**body, "discount_value": 0})).status_code == 422
    assert (await act("inst").post("/promotions", json={**body, "end_date": str(TODAY - timedelta(days=1))})).status_code == 422
    assert (await act("inst").delete(f"/promotions/{p['id']}")).status_code == 204


async def test_dashboard_aggregates(actor, db_conn_and_sessionmaker):
    act, people = actor
    type_id = await _setup(db_conn_and_sessionmaker, people)
    cust = people["cust"][0]
    async with db_conn_and_sessionmaker() as s:
        cp = (await s.execute(
            text("insert into public.customer_passes (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total, sessions_used)"
                 " values (:t, :c, :i, '10회권', 1, 10, 3) returning id"), {"t": type_id, "c": str(cust), "i": str(people["inst"][0])})).scalar_one()
        for amount, method, pass_id, status in ((500000, "CASH", cp, "COMPLETED"), (30000, "TRANSFER", None, "COMPLETED"), (9999, "CASH", None, "REFUNDED")):
            await s.execute(text("insert into public.payments (customer_id, customer_pass_id, amount, method, status) values (:c, :p, :a, :m, :s)"),
                            {"c": str(cust), "p": pass_id, "a": amount, "m": method, "s": status})
        await s.commit()

    d = (await act("inst").get("/instructors/me/dashboard?months=6")).json()
    assert len(d["months"]) == 6 and d["months"][-1]["amount"] == 530000 and d["this_month"] == 530000
    assert d["by_method"][0] == {"method": "CASH", "amount": 500000}
    assert {x["pass_name"]: x["amount"] for x in d["by_pass"]} == {"10회권": 500000, "수강권 미연결": 30000}
    assert d["customers"]["total"] == 1 and d["passes"] == {"active": 1, "remaining_sessions": 7, "completed": 0}
    # 다른 강사는 0, 고객은 볼 수 없음
    assert (await act("rival").get("/instructors/me/dashboard")).json()["this_month"] == 0
    assert (await act("cust").get("/instructors/me/dashboard")).status_code == 403
