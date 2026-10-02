"""회원: 내 정보, 역할별 목록·상세, 담당 고객 등록, 계정 생성·수정·삭제 권한"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.conftest import insert_user

pytestmark = pytest.mark.asyncio


async def _people(db, people):
    async with db() as s:
        inst = await insert_user(s, "INSTRUCTOR")
        people["inst"] = (inst, "INSTRUCTOR")
        people["rival"] = (await insert_user(s, "INSTRUCTOR"), "INSTRUCTOR")
        people["mine"] = (await insert_user(s, "CUSTOMER", manager_id=inst), "CUSTOMER")
        people["free"] = (await insert_user(s, "CUSTOMER"), "CUSTOMER")
        people["admin"] = (await insert_user(s, "ADMIN"), "ADMIN")
        emails = dict((await s.execute(text("select id::text, email from public.users where id = any(:ids)"),
                                       {"ids": [str(v[0]) for v in people.values()]})).all())
    return emails


async def test_me_get_and_update(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    r = await act("mine").patch("/users/me", json={"display_name": "새 이름", "phone": "010-0000-0000", "recurring_off_days": [6, 0, 0]})
    assert r.status_code == 200 and r.json()["display_name"] == "새 이름" and r.json()["recurring_off_days"] == [0, 6]
    assert (await act("mine").patch("/users/me", json={"recurring_off_days": [7]})).status_code == 422
    assert (await act("mine").patch("/users/me", json={"role": "ADMIN"})).status_code == 422  # 역할은 바꿀 수 없다
    taken = (await act("free").get("/users/me")).json()["username"]
    assert (await act("mine").patch("/users/me", json={"username": taken})).status_code == 409
    assert (await act("mine").get("/users/me")).json()["display_name"] == "새 이름"


async def test_list_by_role(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    ids = lambda r: {u["id"] for u in r.json()["items"]}  # noqa: E731

    assert ids(await act("inst").get("/users")) == {str(people["mine"][0])}           # 담당 고객만
    assert ids(await act("free").get("/users")) == {str(people["free"][0])}           # 본인만
    admin_all = await act("admin").get("/users", params={"role": "CUSTOMER", "limit": 200})
    assert {str(people["mine"][0]), str(people["free"][0])} <= ids(admin_all)
    assert all(u["role"] == "CUSTOMER" for u in admin_all.json()["items"])


async def test_detail_permissions(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine, free, inst = (str(people[k][0]) for k in ("mine", "free", "inst"))

    assert (await act("inst").get(f"/users/{mine}")).status_code == 200
    assert (await act("inst").get(f"/users/{free}")).status_code == 403
    assert (await act("mine").get(f"/users/{inst}")).status_code == 200      # 고객 → 담당 강사
    assert (await act("mine").get(f"/users/{free}")).status_code == 403
    assert (await act("admin").get(f"/users/{free}")).status_code == 200
    assert (await act("admin").get(f"/users/{uuid.uuid4()}")).status_code == 404


async def test_register_customer_by_email(actor, db_conn_and_sessionmaker):
    act, people = actor
    emails = await _people(db_conn_and_sessionmaker, people)
    free_email = emails[str(people["free"][0])]

    r = await act("inst").post("/users/me/customers", json={"email": free_email})
    assert r.status_code == 200 and r.json()["manager_id"] == str(people["inst"][0])
    assert (await act("rival").post("/users/me/customers", json={"email": free_email})).status_code == 409
    assert (await act("inst").post("/users/me/customers", json={"email": "none@example.com"})).status_code == 404
    rival_email = emails[str(people["rival"][0])]
    assert (await act("inst").post("/users/me/customers", json={"email": rival_email})).status_code == 400


async def test_create_update_delete_permissions(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    tag = uuid.uuid4().hex[:8]
    body = {"username": f"new-{tag}", "email": f"new-{tag}@example.com", "display_name": "신규", "password": "Pass-1234"}

    r = await act("inst").post("/users", json=body)
    assert r.status_code == 201 and r.json()["manager_id"] == str(people["inst"][0]) and r.json()["role"] == "CUSTOMER"
    created = r.json()["id"]
    assert (await act("inst").post("/users", json={**body, "username": f"x-{tag}", "email": f"x-{tag}@example.com", "role": "ADMIN"})).status_code == 403
    assert (await act("inst").post("/users", json=body)).status_code == 409
    assert (await act("mine").post("/users", json={**body, "username": f"y-{tag}", "email": f"y-{tag}@example.com"})).status_code == 403

    assert (await act("inst").patch(f"/users/{created}", json={"display_name": "수정"})).json()["display_name"] == "수정"
    assert (await act("rival").patch(f"/users/{created}", json={"display_name": "x"})).status_code == 403
    assert (await act("mine").patch(f"/users/{created}", json={"display_name": "x"})).status_code == 403

    assert (await act("rival").delete(f"/users/{created}")).status_code == 403
    assert (await act("mine").delete(f"/users/{created}")).status_code == 403
    assert (await act("inst").delete(f"/users/{created}")).status_code == 204
    assert (await act("admin").delete(f"/users/{created}")).status_code == 404


# ── 결제 기록 보존 기간 (5년) ─────────────────────────────────

async def _payment(db, customer_id, years_ago: int, days: int = 0):
    async with db() as s:
        await s.execute(
            text(
                """
                insert into public.payments (customer_id, amount, method, status, created_at, updated_at)
                values (:c, 10000, 'CASH', 'COMPLETED', now() - make_interval(years => :y, days => :d), now())
                """
            ),
            {"c": str(customer_id), "y": years_ago, "d": days},
        )
        await s.commit()


async def test_customer_with_recent_payment_cannot_be_deleted(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine = people["mine"][0]
    await _payment(db_conn_and_sessionmaker, mine, years_ago=4, days=300)   # 5년 안 됨

    r = await act("inst").delete(f"/users/{mine}")
    assert r.status_code == 409 and "5년" in r.text
    assert (await act("admin").delete(f"/users/{mine}")).status_code == 409   # 관리자도 불가
    assert (await act("admin").get(f"/users/{mine}")).status_code == 200


async def test_customer_with_only_expired_payments_is_deleted_with_them(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine = people["mine"][0]
    await _payment(db_conn_and_sessionmaker, mine, years_ago=5, days=1)     # 5년 지남

    assert (await act("inst").delete(f"/users/{mine}")).status_code == 204
    async with db_conn_and_sessionmaker() as s:
        left = (await s.execute(text("select count(*) from public.payments where customer_id = :c"), {"c": str(mine)})).scalar_one()
    assert left == 0


async def test_db_blocks_cascading_payment_delete(db_conn_and_sessionmaker):
    """앱을 거치지 않고 지워도 DB 가 결제 기록을 지키는지 (ON DELETE RESTRICT)"""
    from sqlalchemy.exc import IntegrityError

    async with db_conn_and_sessionmaker() as s:
        uid = await insert_user(s, "CUSTOMER")
    await _payment(db_conn_and_sessionmaker, uid, years_ago=0)
    async with db_conn_and_sessionmaker() as s:
        with pytest.raises(IntegrityError):
            await s.execute(text("delete from public.users where id = :u"), {"u": str(uid)})
            await s.flush()


# ── 계약 기록(멤버십·수강권) 보존 기간 (5년, 마지막 변경 기준) ──────────

async def _membership(db, customer_id, instructor_id, years_ago: int, days: int = 0):
    async with db() as s:
        await s.execute(
            text(
                """
                insert into public.memberships (customer_id, instructor_id, type, total_count, remaining_count, is_active, created_at, updated_at)
                values (:c, :i, 'TIMES', 10, 3, true,
                        now() - make_interval(years => :y, days => :d), now() - make_interval(years => :y, days => :d))
                """
            ),
            {"c": str(customer_id), "i": str(instructor_id), "y": years_ago, "d": days},
        )
        await s.commit()


async def _customer_pass(db, customer_id, instructor_id, years_ago: int, days: int = 0):
    async with db() as s:
        type_id = (await s.execute(
            text(
                """
                insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, is_active)
                values (:i, '10회권', 1, 10, true) returning id
                """
            ),
            {"i": str(instructor_id)},
        )).scalar_one()
        await s.execute(
            text(
                """
                insert into public.customer_passes
                  (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total, sessions_used, status, created_at, updated_at)
                values (:t, :c, :i, '10회권', 1, 10, 10, 'COMPLETED',
                        now() - make_interval(years => :y, days => :d), now() - make_interval(years => :y, days => :d))
                """
            ),
            {"t": type_id, "c": str(customer_id), "i": str(instructor_id), "y": years_ago, "d": days},
        )
        await s.commit()


async def _count(db, sql: str, uid) -> int:
    async with db() as s:
        return (await s.execute(text(sql), {"u": str(uid)})).scalar_one()


@pytest.mark.parametrize("record", ["membership", "pass"])
async def test_recent_contract_record_blocks_delete_of_customer_and_instructor(actor, db_conn_and_sessionmaker, record):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine, inst = people["mine"][0], people["inst"][0]
    make = _membership if record == "membership" else _customer_pass
    await make(db_conn_and_sessionmaker, mine, inst, years_ago=4, days=300)   # 5년 안 됨

    r = await act("admin").delete(f"/users/{mine}")
    assert r.status_code == 409 and ("멤버십" if record == "membership" else "수강권") in r.text and "withdraw" in r.text
    # 강사를 지워도 고객과의 계약 기록이 사라지면 안 된다
    assert (await act("admin").delete(f"/users/{inst}")).status_code == 409


async def test_expired_contract_records_are_deleted_with_member(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine, inst = people["mine"][0], people["inst"][0]
    db = db_conn_and_sessionmaker
    await _membership(db, mine, inst, years_ago=5, days=1)
    await _customer_pass(db, mine, inst, years_ago=5, days=1)

    assert (await act("admin").delete(f"/users/{mine}")).status_code == 204
    assert await _count(db, "select count(*) from public.memberships where customer_id = :u", mine) == 0
    assert await _count(db, "select count(*) from public.customer_passes where customer_id = :u", mine) == 0
    # 발급 기록이 남지 않은 강사의 수강권 상품은 강사 삭제 때 함께 정리된다
    assert (await act("admin").delete(f"/users/{inst}")).status_code == 204
    assert await _count(db, "select count(*) from public.lesson_pass_types where instructor_id = :u", inst) == 0


@pytest.mark.parametrize("table", ["memberships", "customer_passes"])
async def test_db_blocks_cascading_contract_delete(db_conn_and_sessionmaker, table):
    """앱을 거치지 않고 지워도 DB 가 계약 기록을 지키는지 (ON DELETE RESTRICT)"""
    from sqlalchemy.exc import IntegrityError

    db = db_conn_and_sessionmaker
    async with db() as s:
        cust, inst = await insert_user(s, "CUSTOMER"), await insert_user(s, "INSTRUCTOR")
    await (_membership if table == "memberships" else _customer_pass)(db, cust, inst, years_ago=0)
    for uid in (cust, inst):
        async with db() as s:
            with pytest.raises(IntegrityError):
                await s.execute(text("delete from public.users where id = :u"), {"u": str(uid)})
                await s.flush()


# ── 탈퇴 처리 ─────────────────────────────────────────────────

async def test_withdraw_keeps_payments_and_anonymizes(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine = people["mine"][0]
    await _payment(db_conn_and_sessionmaker, mine, years_ago=1)

    r = await act("inst").delete(f"/users/{mine}")
    assert r.status_code == 409 and "withdraw" in r.text            # 삭제 대신 탈퇴 처리 안내

    r = await act("mine").post("/users/me/withdraw")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "WITHDRAWN" and body["is_active"] is False
    assert body["email"] is None and body["phone"] is None and body["display_name"] == "탈퇴한 회원"
    assert body["manager_id"] is None and body["username"].startswith("withdrawn_")

    async with db_conn_and_sessionmaker() as s:
        kept = (await s.execute(text("select count(*) from public.payments where customer_id = :c"), {"c": str(mine)})).scalar_one()
    assert kept == 1                                                   # 결제 기록은 그대로
    assert body["withdrawn_at"] is not None                            # 탈퇴 시각 기록
    assert (await act("mine").post("/users/me/withdraw")).status_code == 200   # 다시 해도 그대로


async def test_withdraw_permissions_and_managed_customers(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine, free, inst = (people[k][0] for k in ("mine", "free", "inst"))

    assert (await act("rival").post(f"/users/{mine}/withdraw")).status_code == 403   # 남의 고객
    assert (await act("free").post(f"/users/{mine}/withdraw")).status_code == 403    # 고객은 남을 못 함
    assert (await act("inst").post(f"/users/{free}/withdraw")).status_code == 403    # 담당 아닌 고객

    # 강사 본인이 탈퇴하면 담당 고객은 담당 강사가 없는 상태
    assert (await act("inst").post("/users/me/withdraw")).status_code == 200
    assert (await act("admin").get(f"/users/{mine}")).json()["manager_id"] is None
    assert (await act("admin").post(f"/users/{free}/withdraw")).json()["status"] == "WITHDRAWN"


async def test_withdraw_keeps_contract_records(actor, db_conn_and_sessionmaker):
    act, people = actor
    await _people(db_conn_and_sessionmaker, people)
    mine, inst = people["mine"][0], people["inst"][0]
    db = db_conn_and_sessionmaker
    await _membership(db, mine, inst, years_ago=0)
    await _customer_pass(db, mine, inst, years_ago=0)

    assert (await act("mine").post("/users/me/withdraw")).status_code == 200
    assert (await act("inst").post("/users/me/withdraw")).status_code == 200
    assert await _count(db, "select count(*) from public.memberships where customer_id = :u", mine) == 1
    assert await _count(db, "select count(*) from public.customer_passes where customer_id = :u", mine) == 1

