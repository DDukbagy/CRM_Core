from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_create_times_membership(instructor_client, managed_customer_id):
    """강사가 담당 고객에게 횟수제 멤버십 생성."""
    res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "TIMES",
        "total_count": 10,
        "started_at": date.today().isoformat(),
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "TIMES"
    assert body["total_count"] == 10
    assert body["remaining_count"] == 10
    assert body["is_active"] is True


async def test_create_period_membership(instructor_client, managed_customer_id):
    """강사가 담당 고객에게 기간제 멤버십 생성."""
    expires = (date.today() + timedelta(days=90)).isoformat()
    res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "PERIOD",
        "started_at": date.today().isoformat(),
        "expires_at": expires,
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "PERIOD"
    assert body["expires_at"] == expires
    assert body["is_active"] is True


async def test_cannot_create_for_unmanaged_customer(instructor_client, db_conn_and_sessionmaker):
    """담당하지 않는 고객에게 멤버십 생성 시 403."""
    cust_id = str(uuid4())
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role, feedback_consent) "
                "VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'CUSTOMER', true)"
            ),
            {
                "id": cust_id,
                "username": f"unmanaged-{cust_id[:8]}",
                "email": f"unmanaged-{cust_id[:8]}@example.com",
                "display_name": "Unmanaged Customer",
            },
        )
        await session.commit()

    res = await instructor_client.post("/memberships", json={
        "customer_id": cust_id,
        "type": "TIMES",
        "total_count": 5,
    })
    assert res.status_code == 403, res.text


async def test_times_without_total_count_returns_422(instructor_client, managed_customer_id):
    """TIMES 타입에 total_count 없으면 422."""
    res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "TIMES",
    })
    assert res.status_code == 422, res.text


async def test_period_without_expires_at_returns_422(instructor_client, managed_customer_id):
    """PERIOD 타입에 expires_at 없으면 422."""
    res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "PERIOD",
        "started_at": date.today().isoformat(),
    })
    assert res.status_code == 422, res.text


async def test_update_remaining_count(instructor_client, managed_customer_id):
    """잔여 횟수 수동 조정."""
    create_res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "TIMES",
        "total_count": 10,
    })
    assert create_res.status_code == 201, create_res.text
    membership_id = create_res.json()["id"]

    patch_res = await instructor_client.patch(f"/memberships/{membership_id}", json={
        "remaining_count": 7,
    })
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()["remaining_count"] == 7


async def test_deactivate_membership(instructor_client, managed_customer_id):
    """멤버십 비활성화."""
    create_res = await instructor_client.post("/memberships", json={
        "customer_id": str(managed_customer_id),
        "type": "TIMES",
        "total_count": 5,
    })
    assert create_res.status_code == 201, create_res.text
    membership_id = create_res.json()["id"]

    patch_res = await instructor_client.patch(f"/memberships/{membership_id}", json={
        "is_active": False,
    })
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()["is_active"] is False


async def test_instructor_cannot_patch_others_membership(
    db_conn_and_sessionmaker, instructor_client
):
    """다른 강사의 멤버십은 수정 불가 (403)."""
    other_instr_id = str(uuid4())
    other_cust_id = str(uuid4())
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role, feedback_consent) "
                "VALUES (:id, :username, :email, :dn, true, 'ACTIVE', 'INSTRUCTOR', true)"
            ),
            {
                "id": other_instr_id,
                "username": f"other-{other_instr_id[:8]}",
                "email": f"other-{other_instr_id[:8]}@example.com",
                "dn": "Other Instructor",
            },
        )
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role, manager_id, feedback_consent) "
                "VALUES (:id, :username, :email, :dn, true, 'ACTIVE', 'CUSTOMER', :mid, true)"
            ),
            {
                "id": other_cust_id,
                "username": f"ocust-{other_cust_id[:8]}",
                "email": f"ocust-{other_cust_id[:8]}@example.com",
                "dn": "Other Customer",
                "mid": other_instr_id,
            },
        )
        res_id = await session.execute(
            text(
                "INSERT INTO public.memberships (customer_id, instructor_id, type, total_count, remaining_count, is_active) "
                "VALUES (:cid, :iid, 'TIMES', 5, 5, true) RETURNING id"
            ),
            {"cid": other_cust_id, "iid": other_instr_id},
        )
        membership_id = res_id.scalar_one()
        await session.commit()

    res = await instructor_client.patch(f"/memberships/{membership_id}", json={"remaining_count": 1})
    assert res.status_code == 403, res.text
