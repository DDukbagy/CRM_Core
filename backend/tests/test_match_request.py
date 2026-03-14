from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_customer_creates_match_request(client, instructor_id):
    """고객 → 강사 MATCH 요청: PENDING 상태, NORMAL 강사는 fee=0."""
    res = await client.post("/instructors/match", json={
        "instructor_id": str(instructor_id),
        "request_type": "MATCH",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "PENDING"
    assert body["request_type"] == "MATCH"
    assert body["fee"] == 0


async def test_named_instructor_match_has_fee(client, named_instructor_id):
    """NAMED 강사에게 MATCH 요청 시 수수료 5000원."""
    res = await client.post("/instructors/match", json={
        "instructor_id": str(named_instructor_id),
        "request_type": "MATCH",
    })
    assert res.status_code == 201, res.text
    assert res.json()["fee"] == 5000


async def test_consultation_is_always_free(client, named_instructor_id):
    """NAMED 강사에게 CONSULTATION 요청도 항상 무료."""
    res = await client.post("/instructors/match", json={
        "instructor_id": str(named_instructor_id),
        "request_type": "CONSULTATION",
    })
    assert res.status_code == 201, res.text
    assert res.json()["fee"] == 0


async def test_duplicate_match_returns_409(client, instructor_id):
    """동일 MATCH 요청 중복 시 409."""
    payload = {"instructor_id": str(instructor_id), "request_type": "MATCH"}
    first = await client.post("/instructors/match", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/instructors/match", json=payload)
    assert second.status_code == 409, second.text


async def test_duplicate_consultation_returns_409(client, instructor_id):
    """동일 CONSULTATION 요청 중복 시 409."""
    payload = {"instructor_id": str(instructor_id), "request_type": "CONSULTATION"}
    first = await client.post("/instructors/match", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/instructors/match", json=payload)
    assert second.status_code == 409, second.text


async def test_match_and_consultation_can_coexist(client, instructor_id):
    """MATCH 와 CONSULTATION 요청은 동시에 존재할 수 있다."""
    match_res = await client.post("/instructors/match", json={
        "instructor_id": str(instructor_id),
        "request_type": "MATCH",
    })
    assert match_res.status_code == 201, match_res.text

    consult_res = await client.post("/instructors/match", json={
        "instructor_id": str(instructor_id),
        "request_type": "CONSULTATION",
    })
    assert consult_res.status_code == 201, consult_res.text


async def test_instructor_accepts_match_request(
    db_conn_and_sessionmaker, instructor_client, instructor_id
):
    """강사가 MATCH 요청 수락 → status=ACCEPTED."""
    cust_id = str(uuid4())
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role) "
                "VALUES (:id, :username, :email, :dn, true, 'ACTIVE', 'CUSTOMER')"
            ),
            {
                "id": cust_id,
                "username": f"cust-acc-{cust_id[:8]}",
                "email": f"cust-acc-{cust_id[:8]}@example.com",
                "dn": "Accept Test Customer",
            },
        )
        await session.execute(
            text(
                "INSERT INTO public.instructor_match_requests "
                "(customer_id, instructor_id, request_type, status, fee) "
                "VALUES (:cid, :iid, 'MATCH', 'PENDING', 0)"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        await session.commit()
        row = await session.execute(
            text(
                "SELECT id FROM public.instructor_match_requests "
                "WHERE customer_id = :cid AND instructor_id = :iid "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        request_id = row.scalar_one()

    res = await instructor_client.patch(f"/instructors/match/{request_id}/accept")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ACCEPTED"


async def test_instructor_rejects_match_request(
    db_conn_and_sessionmaker, instructor_client, instructor_id
):
    """강사가 MATCH 요청 거절 → status=REJECTED."""
    cust_id = str(uuid4())
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role) "
                "VALUES (:id, :username, :email, :dn, true, 'ACTIVE', 'CUSTOMER')"
            ),
            {
                "id": cust_id,
                "username": f"cust-rej-{cust_id[:8]}",
                "email": f"cust-rej-{cust_id[:8]}@example.com",
                "dn": "Reject Test Customer",
            },
        )
        await session.execute(
            text(
                "INSERT INTO public.instructor_match_requests "
                "(customer_id, instructor_id, request_type, status, fee) "
                "VALUES (:cid, :iid, 'MATCH', 'PENDING', 0)"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        await session.commit()
        row = await session.execute(
            text(
                "SELECT id FROM public.instructor_match_requests "
                "WHERE customer_id = :cid AND instructor_id = :iid "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        request_id = row.scalar_one()

    res = await instructor_client.patch(f"/instructors/match/{request_id}/reject")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "REJECTED"


async def test_customer_cancels_match_request(client, instructor_id):
    """고객이 PENDING 요청 취소 → 204."""
    create_res = await client.post("/instructors/match", json={
        "instructor_id": str(instructor_id),
        "request_type": "MATCH",
    })
    assert create_res.status_code == 201, create_res.text
    request_id = create_res.json()["id"]

    cancel_res = await client.delete(f"/instructors/match/{request_id}")
    assert cancel_res.status_code == 204, cancel_res.text


async def test_cannot_cancel_accepted_request(
    db_conn_and_sessionmaker, client, instructor_id
):
    """ACCEPTED 상태 요청은 취소 불가 (400)."""
    # client fixture 의 실제 user id를 API로 확인
    me_res = await client.get("/users/me")
    assert me_res.status_code == 200, me_res.text
    cust_id = me_res.json()["id"]

    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO public.instructor_match_requests "
                "(customer_id, instructor_id, request_type, status, fee) "
                "VALUES (:cid, :iid, 'MATCH', 'ACCEPTED', 0)"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        await session.commit()
        row = await session.execute(
            text(
                "SELECT id FROM public.instructor_match_requests "
                "WHERE customer_id = :cid AND instructor_id = :iid AND status='ACCEPTED' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": cust_id, "iid": str(instructor_id)},
        )
        request_id = row.scalar_one()

    res = await client.delete(f"/instructors/match/{request_id}")
    assert res.status_code == 400, res.text
