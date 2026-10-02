from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.domains.payment.router as payment_router
from tests.conftest import _ensure_customer_managed_by, _ensure_instructor

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
def _reset_payment_rate_limit():
    """결제 등록은 분당 20회 제한이 있어 테스트끼리 횟수가 누적되지 않게 초기화한다."""
    payment_router.limiter.reset()
    yield
    payment_router.limiter.reset()


async def _insert_membership(session: AsyncSession, customer_id: uuid.UUID, instructor_id: uuid.UUID) -> uuid.UUID:
    membership_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.memberships (id, customer_id, instructor_id, type, total_count, remaining_count, started_at, is_active)
            values (:id, :customer_id, :instructor_id, 'TIMES', 10, 10, :started_at, true)
            """
        ),
        {
            "id": str(membership_id),
            "customer_id": str(customer_id),
            "instructor_id": str(instructor_id),
            "started_at": date.today(),
        },
    )
    await session.commit()
    return membership_id


async def _insert_payment(session: AsyncSession, customer_id: uuid.UUID, amount: int = 10000) -> uuid.UUID:
    payment_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.payments (id, customer_id, amount, method, status)
            values (:id, :customer_id, :amount, 'CASH', 'COMPLETED')
            """
        ),
        {"id": str(payment_id), "customer_id": str(customer_id), "amount": amount},
    )
    await session.commit()
    return payment_id


# ── 등록 ──────────────────────────────────────────────────────

async def test_instructor_records_payment_for_managed_customer(instructor_client, managed_customer_id):
    res = await instructor_client.post("/payments", json={
        "customer_id": str(managed_customer_id),
        "amount": 50000,
        "method": "CASH",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["customer_id"] == str(managed_customer_id)
    assert body["amount"] == 50000
    assert body["method"] == "CASH"
    assert body["status"] == "COMPLETED"
    assert body["membership_id"] is None


async def test_payment_linked_to_own_membership(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        membership_id = await _insert_membership(session, managed_customer_id, instructor_id)

    res = await instructor_client.post("/payments", json={
        "customer_id": str(managed_customer_id),
        "membership_id": str(membership_id),
        "amount": 300000,
        "method": "TRANSFER",
    })
    assert res.status_code == 201, res.text
    assert res.json()["membership_id"] == str(membership_id)


async def test_instructor_cannot_record_payment_for_unmanaged_customer(
    instructor_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        other_instructor = await _ensure_instructor(session)
        other_customer = await _ensure_customer_managed_by(session, other_instructor)

    res = await instructor_client.post("/payments", json={
        "customer_id": str(other_customer),
        "amount": 50000,
        "method": "CASH",
    })
    assert res.status_code == 403, res.text


async def test_membership_of_another_customer_is_rejected(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        another_customer = await _ensure_customer_managed_by(session, instructor_id)
        membership_id = await _insert_membership(session, another_customer, instructor_id)

    res = await instructor_client.post("/payments", json={
        "customer_id": str(managed_customer_id),
        "membership_id": str(membership_id),
        "amount": 50000,
        "method": "CASH",
    })
    assert res.status_code == 400, res.text


async def test_membership_created_by_another_instructor_is_rejected(
    instructor_client, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        other_instructor = await _ensure_instructor(session)
        membership_id = await _insert_membership(session, managed_customer_id, other_instructor)

    res = await instructor_client.post("/payments", json={
        "customer_id": str(managed_customer_id),
        "membership_id": str(membership_id),
        "amount": 50000,
        "method": "CASH",
    })
    assert res.status_code == 403, res.text


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"amount": 50000, "method": "BITCOIN"}, 400),
        ({"amount": 0, "method": "CASH"}, 400),
        ({"amount": -1000, "method": "CASH"}, 400),
        ({"amount": 50000, "method": "CASH", "status": "REFUNDED"}, 422),  # 정의 안 된 필드
        ({"method": "CASH"}, 422),  # 금액 누락
    ],
)
async def test_invalid_payment_is_rejected(instructor_client, managed_customer_id, payload, status):
    res = await instructor_client.post("/payments", json={"customer_id": str(managed_customer_id), **payload})
    assert res.status_code == status, res.text


async def test_unknown_customer_or_membership_is_404(instructor_client, managed_customer_id):
    res = await instructor_client.post("/payments", json={"customer_id": str(uuid.uuid4()), "amount": 1000, "method": "CASH"})
    assert res.status_code == 404, res.text

    res = await instructor_client.post("/payments", json={
        "customer_id": str(managed_customer_id), "membership_id": str(uuid.uuid4()), "amount": 1000, "method": "CASH",
    })
    assert res.status_code == 404, res.text


async def test_customer_cannot_record_payment(client):
    me = (await client.get("/users/me")).json()
    res = await client.post("/payments", json={"customer_id": me["id"], "amount": 1000, "method": "CASH"})
    assert res.status_code == 403, res.text


async def test_create_payment_rate_limit(instructor_client, managed_customer_id):
    body = {"customer_id": str(managed_customer_id), "amount": 1000, "method": "CASH"}
    for _ in range(20):
        assert (await instructor_client.post("/payments", json=body)).status_code == 201
    assert (await instructor_client.post("/payments", json=body)).status_code == 429


# ── 조회 ──────────────────────────────────────────────────────

async def test_instructor_lists_only_managed_customers_payments(
    instructor_client, instructor_id, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        mine = await _insert_payment(session, managed_customer_id)
        other_instructor = await _ensure_instructor(session)
        other_customer = await _ensure_customer_managed_by(session, other_instructor)
        others = await _insert_payment(session, other_customer)

    res = await instructor_client.get("/payments")
    assert res.status_code == 200, res.text
    ids = {p["id"] for p in res.json()}
    assert str(mine) in ids
    assert str(others) not in ids

    res = await instructor_client.get("/payments", params={"customer_id": str(other_customer)})
    assert res.status_code == 200
    assert res.json() == []


async def test_customer_lists_only_own_payments(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    me = uuid.UUID((await client.get("/users/me")).json()["id"])
    async with db_conn_and_sessionmaker() as session:
        mine = await _insert_payment(session, me)
        instructor = await _ensure_instructor(session)
        someone = await _ensure_customer_managed_by(session, instructor)
        others = await _insert_payment(session, someone)

    res = await client.get("/payments")
    assert res.status_code == 200, res.text
    ids = {p["id"] for p in res.json()}
    assert str(mine) in ids
    assert str(others) not in ids


# ── 상태 변경 (관리자) ────────────────────────────────────────

async def test_admin_updates_payment_status(admin_client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    async with db_conn_and_sessionmaker() as session:
        instructor = await _ensure_instructor(session)
        customer = await _ensure_customer_managed_by(session, instructor)
        payment_id = await _insert_payment(session, customer)

    res = await admin_client.patch(f"/payments/{payment_id}/status", json={"status": "REFUNDED"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "REFUNDED"

    res = await admin_client.patch(f"/payments/{payment_id}/status", json={"status": "PENDING"})
    assert res.status_code == 400, res.text

    res = await admin_client.patch(f"/payments/{uuid.uuid4()}/status", json={"status": "FAILED"})
    assert res.status_code == 404, res.text


async def test_instructor_cannot_update_payment_status(
    instructor_client, managed_customer_id, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        payment_id = await _insert_payment(session, managed_customer_id)

    res = await instructor_client.patch(f"/payments/{payment_id}/status", json={"status": "REFUNDED"})
    assert res.status_code == 403, res.text
