"""강사 관리: 스태프, 강사 신청·승인, 공개 목록, 전화번호 조회·담당 등록, 통계"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import insert_user

pytestmark = pytest.mark.asyncio


async def _setup(db, people, **extra):
    async with db() as s:
        people["inst"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["staff"] = (await insert_user(s, "CONTENT_MANAGER"), "CONTENT_MANAGER")
        people["cust"] = (await insert_user(s, "CUSTOMER", phone="010-1111-2222"), "CUSTOMER")
        people["admin"] = (await insert_user(s, "ADMIN"), "ADMIN")
        for name, (role, kw) in extra.items():
            people[name] = (await insert_user(s, role, **kw), role)
        rows = (await s.execute(text("select id, email from public.users where id = any(:ids)"),
                                {"ids": [str(v[0]) for v in people.values()]})).all()
    return {str(r[0]): r[1] for r in rows}


async def test_staff_add_list_remove(actor, db_conn_and_sessionmaker):
    act, people = actor
    emails = await _setup(db_conn_and_sessionmaker, people)
    staff_id, staff_email = people["staff"][0], emails[str(people["staff"][0])]

    inst = act("inst")
    assert (await inst.post("/instructors/me/staff", json={"staff_email": staff_email})).status_code == 201
    assert (await inst.post("/instructors/me/staff", json={"staff_email": staff_email})).status_code == 409
    assert (await inst.post("/instructors/me/staff", json={"staff_email": "nobody@example.com"})).status_code == 404
    me_email = emails[str(people["inst"][0])]
    assert (await inst.post("/instructors/me/staff", json={"staff_email": me_email})).status_code == 400

    listed = (await inst.get("/instructors/me/staff")).json()
    assert [s["staff_user_id"] for s in listed] == [str(staff_id)] and listed[0]["email"] == staff_email

    assert (await inst.delete(f"/instructors/me/staff/{staff_id}")).status_code == 204
    assert (await inst.delete(f"/instructors/me/staff/{staff_id}")).status_code == 404
    assert (await act("cust").get("/instructors/me/staff")).status_code == 403


async def test_apply_and_approve(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _setup(db_conn_and_sessionmaker, people)
    cust_id = people["cust"][0]

    r = await act("cust").post("/instructors/apply")
    assert r.status_code == 200 and r.json()["status"] == "PENDING" and r.json()["role"] == "INSTRUCTOR"
    pending = (await act("admin").get("/instructors/pending")).json()
    assert str(cust_id) in [p["id"] for p in pending]
    assert (await act("inst").get("/instructors/pending")).status_code == 403

    r = await act("admin").post(f"/instructors/{cust_id}/approve")
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    assert (await act("admin").post(f"/instructors/{people['staff'][0]}/approve")).status_code == 404  # 강사 아님
    assert (await act("inst").post(f"/instructors/{cust_id}/approve")).status_code == 403
    assert (await act("inst").post("/instructors/apply")).status_code == 403  # 고객만 신청


async def test_public_list_filters_and_order(actor, db_conn_and_sessionmaker):
    act, people = actor
    tag = uuid.uuid4().hex[:6]
    await _setup(db_conn_and_sessionmaker, people,
                 named=("INSTRUCTOR", {"instructor_tier": "NAMED", "instructor_location": f"서울{tag}",
                                       "instructor_specialties": "퍼팅, 스윙", "display_name": f"zz-{tag}"}),
                 normal=("INSTRUCTOR", {"instructor_location": f"서울{tag}", "instructor_specialties": "스윙",
                                        "display_name": f"aa-{tag}"}),
                 pending=("INSTRUCTOR", {"status": "PENDING", "instructor_location": f"서울{tag}"}))
    r = await act("cust").get("/instructors/public", params={"location": f"서울{tag}"})
    assert r.status_code == 200
    body = r.json()
    assert [i["id"] for i in body] == [str(people["named"][0]), str(people["normal"][0])]  # NAMED 우선, 승인 대기 제외
    assert body[0]["match_fee"] > 0 and body[1]["match_fee"] == 0 and body[0]["specialties"] == ["퍼팅", "스윙"]

    r = await act("cust").get("/instructors/public", params={"location": f"서울{tag}", "specialty": "퍼팅"})
    assert [i["id"] for i in r.json()] == [str(people["named"][0])]
    r = await act("cust").get("/instructors/public", params={"name": f"aa-{tag}"})
    assert [i["id"] for i in r.json()] == [str(people["normal"][0])]


async def test_lookup_and_assign_customer(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _setup(db_conn_and_sessionmaker, people, rival=("INSTRUCTOR", {}))
    inst, cust_id = act("inst"), people["cust"][0]

    r = await inst.get("/instructors/customers/lookup", params={"phone": "010-1111-2222"})
    assert r.status_code == 200 and r.json()["id"] == str(cust_id) and r.json()["is_my_customer"] is False
    assert (await inst.get("/instructors/customers/lookup", params={"phone": "000"})).status_code == 404

    r = await inst.post(f"/instructors/customers/{cust_id}/assign")
    assert r.status_code == 200 and r.json()["manager_id"] == str(people["inst"][0])
    r = await act("inst").get("/instructors/customers/lookup", params={"phone": "010-1111-2222"})
    assert r.json()["is_my_customer"] is True and r.json()["manager_name"]

    assert (await act("rival").post(f"/instructors/customers/{cust_id}/assign")).status_code == 409
    assert (await act("inst").post(f"/instructors/customers/{people['staff'][0]}/assign")).status_code == 400
    assert (await act("inst").post(f"/instructors/customers/{uuid.uuid4()}/assign")).status_code == 404
    assert (await act("cust").get("/instructors/customers/lookup", params={"phone": "x"})).status_code == 403


async def test_stats(actor, db_conn_and_sessionmaker):
    act, people = actor
    async with db_conn_and_sessionmaker() as s:
        inst = await insert_user(s, "INSTRUCTOR")
        c1 = await insert_user(s, "CUSTOMER", manager_id=inst)
        c2 = await insert_user(s, "CUSTOMER", manager_id=inst)
        other = await insert_user(s, "CUSTOMER")
        cal = (await s.execute(text("insert into public.calendars (topics, description, host_id) values ('[]'::jsonb, 'c', :h) returning id"), {"h": str(inst)})).scalar_one()
        slot = (await s.execute(text("insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id) values ('09:00','10:00','[0,1,2,3,4,5,6]'::jsonb, true, :c) returning id"), {"c": cal})).scalar_one()
        for i, (guest, st) in enumerate([(c1, "COMPLETED"), (c1, "COMPLETED"), (c1, "NO_SHOW"), (c2, "CONFIRMED"), (other, "COMPLETED")]):
            await s.execute(text("""insert into public.bookings ("when", topic, type, status, time_slot_id, guest_id) values (:d, 't', 'LESSON', :st, :s, :g)"""),
                            {"d": date.today() + timedelta(days=i), "st": st, "s": slot, "g": str(guest)})
        await s.commit()
    people["inst"] = (inst, "INSTRUCTOR")

    r = await act("inst").get("/instructors/me/stats")
    body = r.json()
    assert body["customer_count"] == 2
    assert body["booking_counts"]["total"] == 4 and body["booking_counts"]["completed"] == 2 and body["booking_counts"]["no_show"] == 1
    assert body["attendance_rate"] == 66.7

    r = await act("inst").get(f"/instructors/me/stats/customer/{c1}")
    assert r.json()["booking_counts"]["total"] == 3 and r.json()["attendance_rate"] == 66.7
    assert (await act("inst").get(f"/instructors/me/stats/customer/{other}")).status_code == 404
