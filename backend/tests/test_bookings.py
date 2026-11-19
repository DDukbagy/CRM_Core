# 예약 생성·중복 방지·취소 신청 흐름
from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text

from tests.conftest import insert_pass_for_slot

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def bookable_slot(free_slot_and_date, client, db_conn_and_sessionmaker):
    """conftest 의 빈 슬롯·날짜 + 로그인한 고객(client)에게 그 슬롯 강사의 수강권 (예약하려면 필요)"""
    slot_id, d = free_slot_and_date
    me = (await client.get("/users/me")).json()["id"]
    async with db_conn_and_sessionmaker() as s:
        await insert_pass_for_slot(s, me, slot_id)
    return slot_id, d


async def test_create_booking_success(client, bookable_slot):
    slot_id, d = bookable_slot

    payload = {
        "time_slot_id": slot_id,
        "when": d.isoformat(),
        "topic": "테스트 예약",
        "description": "통합테스트",
    }

    res = await client.post("/bookings", json=payload)
    assert res.status_code == 201, res.text

    body = res.json()
    assert body["time_slot_id"] == slot_id
    assert body["when"] in (d.isoformat(), str(d))  # 모델 직렬화 형태 차이 대비


async def test_create_booking_duplicate_conflict(client, bookable_slot):
    slot_id, d = bookable_slot

    payload = {
        "time_slot_id": slot_id,
        "when": d.isoformat(),
        "topic": "중복 테스트",
        "description": None,
    }

    first = await client.post("/bookings", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/bookings", json=payload)
    assert second.status_code == 409, second.text  # 너 코드에서 409를 의도함


async def test_cancel_then_rebook_allowed(client, bookable_slot, db_conn_and_sessionmaker):
    slot_id, d = bookable_slot

    payload = {
        "time_slot_id": slot_id,
        "when": d.isoformat(),
        "topic": "취소 후 재예약 테스트",
    }

    created = await client.post("/bookings", json=payload)
    assert created.status_code == 201, created.text
    booking_id = created.json().get("id")
    assert booking_id is not None, "BookingRead에 id가 없어서 취소 업데이트가 불가능합니다."

    # DB에서 status를 CANCELLED로 바꿔서 정책 검증 (부분 유니크 인덱스와 일치해야 함)
    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text("update public.bookings set status='CANCELLED' where id = :id"),
            {"id": booking_id},
        )
        await session.commit()

    rebook = await client.post("/bookings", json=payload)
    assert rebook.status_code == 201, rebook.text

async def test_withdraw_requested_booking_success(client, bookable_slot):
    """REQUESTED 상태의 예약은 withdraw로 철회할 수 있어야 한다."""
    slot_id, d = bookable_slot

    payload = {
        "time_slot_id": slot_id,
        "when": d.isoformat(),
        "topic": "요청철회 테스트",
    }

    created = await client.post("/bookings", json=payload)
    assert created.status_code == 201, created.text
    booking_id = created.json().get("id")
    assert booking_id is not None

    res = await client.patch(f"/bookings/{booking_id}/withdraw", json={"reason": "사정이 생김"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "CANCELLED"


async def test_cancel_requested_booking_should_fail(client, bookable_slot):
    """REQUESTED 상태의 예약은 cancel이 아니라 withdraw로만 처리되어야 한다."""
    slot_id, d = bookable_slot

    payload = {
        "time_slot_id": slot_id,
        "when": d.isoformat(),
        "topic": "REQUESTED cancel 차단 테스트",
    }

    created = await client.post("/bookings", json=payload)
    assert created.status_code == 201, created.text
    booking_id = created.json().get("id")
    assert booking_id is not None

    res = await client.patch(f"/bookings/{booking_id}/cancel", json={"reason": "취소"})
    assert res.status_code == 409, res.text


# 취소 신청(CANCEL_REQUESTED) 흐름

async def test_cancel_as_guest_sets_cancel_requested(client, bookable_slot, db_conn_and_sessionmaker):
    """CONFIRMED 예약에 대해 고객이 취소 신청 → CANCEL_REQUESTED."""
    slot_id, d = bookable_slot

    created = await client.post("/bookings", json={
        "time_slot_id": slot_id, "when": d.isoformat(), "topic": "취소신청 테스트",
    })
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text("UPDATE public.bookings SET status='CONFIRMED' WHERE id = :id"),
            {"id": booking_id},
        )
        await session.commit()

    res = await client.patch(f"/bookings/{booking_id}/cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCEL_REQUESTED"


async def test_withdraw_cancel_request_returns_confirmed(client, bookable_slot, db_conn_and_sessionmaker):
    """CANCEL_REQUESTED 상태에서 고객이 취소 신청 철회 → CONFIRMED."""
    slot_id, d = bookable_slot

    created = await client.post("/bookings", json={
        "time_slot_id": slot_id, "when": d.isoformat(), "topic": "취소철회 테스트",
    })
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    async with db_conn_and_sessionmaker() as session:
        await session.execute(
            text("UPDATE public.bookings SET status='CANCEL_REQUESTED' WHERE id = :id"),
            {"id": booking_id},
        )
        await session.commit()

    res = await client.patch(f"/bookings/{booking_id}/withdraw-cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CONFIRMED"


async def test_admin_approve_cancel(admin_client, free_slot_and_date, db_conn_and_sessionmaker):
    """관리자가 취소 신청 승인 → CANCELLED."""
    import uuid as _uuid
    slot_id, d = free_slot_and_date

    async with db_conn_and_sessionmaker() as session:
        cid = _uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role, feedback_consent) "
                "VALUES (:id, :u, :e, :d, true, 'ACTIVE', 'CUSTOMER', true)"
            ),
            {"id": str(cid), "u": f"guest-{cid.hex[:8]}", "e": f"guest-{cid.hex[:8]}@example.com", "d": "Guest"},
        )
        await session.commit()
        guest_id = str(cid)
        cp_id = await insert_pass_for_slot(session, guest_id, slot_id)
        ins = await session.execute(
            text(
                "INSERT INTO public.bookings (\"when\", topic, type, status, time_slot_id, guest_id, customer_pass_id) "
                "VALUES (:when, '취소승인 테스트', 'LESSON', 'CANCEL_REQUESTED', :slot_id, :guest_id, :cp) RETURNING id"
            ),
            {"when": d, "slot_id": slot_id, "guest_id": guest_id, "cp": cp_id},
        )
        booking_id = ins.scalar_one()
        await session.commit()

    res = await admin_client.patch(f"/calendars/me/bookings/{booking_id}/approve-cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"


async def test_admin_reject_cancel(admin_client, free_slot_and_date, db_conn_and_sessionmaker):
    """관리자가 취소 신청 거절 → CONFIRMED 유지."""
    import uuid as _uuid
    slot_id, d = free_slot_and_date

    async with db_conn_and_sessionmaker() as session:
        cid = _uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO public.users (id, username, email, display_name, is_active, status, role, feedback_consent) "
                "VALUES (:id, :u, :e, :d, true, 'ACTIVE', 'CUSTOMER', true)"
            ),
            {"id": str(cid), "u": f"guest-{cid.hex[:8]}", "e": f"guest-{cid.hex[:8]}@example.com", "d": "Guest"},
        )
        await session.commit()
        guest_id = str(cid)
        cp_id = await insert_pass_for_slot(session, guest_id, slot_id)
        ins = await session.execute(
            text(
                "INSERT INTO public.bookings (\"when\", topic, type, status, time_slot_id, guest_id, customer_pass_id) "
                "VALUES (:when, '취소거절 테스트', 'LESSON', 'CANCEL_REQUESTED', :slot_id, :guest_id, :cp) RETURNING id"
            ),
            {"when": d, "slot_id": slot_id, "guest_id": guest_id, "cp": cp_id},
        )
        booking_id = ins.scalar_one()
        await session.commit()

    res = await admin_client.patch(f"/calendars/me/bookings/{booking_id}/reject-cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CONFIRMED"

