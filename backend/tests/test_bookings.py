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
