from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_create_booking_success(client, free_slot_and_date):
    slot_id, d = free_slot_and_date

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


async def test_create_booking_duplicate_conflict(client, free_slot_and_date):
    slot_id, d = free_slot_and_date

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


async def test_cancel_then_rebook_allowed(client, free_slot_and_date, db_conn_and_sessionmaker):
    slot_id, d = free_slot_and_date

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

async def test_withdraw_requested_booking_success(client, free_slot_and_date):
    """REQUESTED 상태의 예약은 withdraw로 철회할 수 있어야 한다."""
    slot_id, d = free_slot_and_date

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


async def test_cancel_requested_booking_should_fail(client, free_slot_and_date):
    """REQUESTED 상태의 예약은 cancel이 아니라 withdraw로만 처리되어야 한다."""
    slot_id, d = free_slot_and_date

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
    assert res.status_code == 400, res.text


# ── CANCEL_REQUESTED 상태 머신 테스트 ─────────────────────────────────────────

async def test_cancel_as_guest_sets_cancel_requested(client, free_slot_and_date, db_conn_and_sessionmaker):
    """CONFIRMED 예약에 대해 고객이 취소 신청 → CANCEL_REQUESTED."""
    slot_id, d = free_slot_and_date

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


async def test_withdraw_cancel_request_returns_confirmed(client, free_slot_and_date, db_conn_and_sessionmaker):
    """CANCEL_REQUESTED 상태에서 고객이 취소 신청 철회 → CONFIRMED."""
    slot_id, d = free_slot_and_date

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
    slot_id, d = free_slot_and_date

    async with db_conn_and_sessionmaker() as session:
        row = await session.execute(text("SELECT id FROM public.users WHERE role='CUSTOMER' LIMIT 1"))
        guest_id = str(row.scalar_one())
        ins = await session.execute(
            text(
                "INSERT INTO public.bookings (\"when\", topic, type, status, time_slot_id, guest_id) "
                "VALUES (:when, '취소승인 테스트', 'LESSON', 'CANCEL_REQUESTED', :slot_id, :guest_id) RETURNING id"
            ),
            {"when": d, "slot_id": slot_id, "guest_id": guest_id},
        )
        booking_id = ins.scalar_one()
        await session.commit()

    res = await admin_client.patch(f"/calendars/me/bookings/{booking_id}/approve-cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"


async def test_admin_reject_cancel(admin_client, free_slot_and_date, db_conn_and_sessionmaker):
    """관리자가 취소 신청 거절 → CONFIRMED 유지."""
    slot_id, d = free_slot_and_date

    async with db_conn_and_sessionmaker() as session:
        row = await session.execute(text("SELECT id FROM public.users WHERE role='CUSTOMER' LIMIT 1"))
        guest_id = str(row.scalar_one())
        ins = await session.execute(
            text(
                "INSERT INTO public.bookings (\"when\", topic, type, status, time_slot_id, guest_id) "
                "VALUES (:when, '취소거절 테스트', 'LESSON', 'CANCEL_REQUESTED', :slot_id, :guest_id) RETURNING id"
            ),
            {"when": d, "slot_id": slot_id, "guest_id": guest_id},
        )
        booking_id = ins.scalar_one()
        await session.commit()

    res = await admin_client.patch(f"/calendars/me/bookings/{booking_id}/reject-cancel")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CONFIRMED"

