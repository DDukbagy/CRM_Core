from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.auth.dependencies import get_current_user, get_current_host

from app.domains.calendar.schemas import (
    CalendarCreate, CalendarUpdate, CalendarRead,
    TimeSlotCreate, TimeSlotRead,
    AvailabilityResponse, AvailabilityDay, AvailabilitySlot,
    BookingCreate, BookingRead, BookingCancelResponse,
)

router = APIRouter(tags=["calendar"])


# -----------------------
# Helpers
# -----------------------

def _parse_json_list(value: Any) -> list:
    """
    DB에서 jsonb를 가져왔을 때 드라이버/설정에 따라
    이미 list로 오거나, str(JSON)로 오는 경우가 있어 통일 처리.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (dict,)):
        # topics/weekday는 list를 기대하지만, 혹시라도 dict면 안전하게 빈 처리
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _weekday_0_mon(d: date) -> int:
    """
    date.weekday(): 월=0 ... 일=6  (우리가 쓰는 요일 체계와 동일)
    """
    return d.weekday()


def _date_range_inclusive(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur = cur + timedelta(days=1)
    return days


# -----------------------
# Host: My Calendar
# -----------------------

@router.post(
    "/calendars/me",
    response_model=CalendarRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_calendar(
    data: CalendarCreate,
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    """
    호스트가 자기 캘린더를 1회 생성.
    - calendars.host_id는 unique라서 호스트당 1개만 허용.
    """
    host_id: UUID = host["id"]

    # 이미 존재하는지 확인
    existing = await session.execute(
        text("""
            SELECT id, host_id, topics, description, created_at, updated_at
            FROM calendars
            WHERE host_id = :host_id
        """),
        {"host_id": str(host_id)},
    )
    row = existing.mappings().first()
    if row:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calendar already exists for this host",
        )

    topics_json = json.dumps(data.topics)

    result = await session.execute(
        text("""
            INSERT INTO calendars (topics, description, host_id)
            VALUES (CAST(:topics AS jsonb), :description, :host_id)
            RETURNING id, host_id, topics, description, created_at, updated_at
        """),
        {
            "topics": topics_json,
            "description": data.description,
            "host_id": str(host_id),
        },
    )
    await session.commit()
    created = result.mappings().one()

    # jsonb 정상화
    created = dict(created)
    created["topics"] = _parse_json_list(created.get("topics"))
    return created


@router.get(
    "/calendars/me",
    response_model=CalendarRead,
)
async def get_my_calendar(
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    host_id: UUID = host["id"]

    result = await session.execute(
        text("""
            SELECT id, host_id, topics, description, created_at, updated_at
            FROM calendars
            WHERE host_id = :host_id
        """),
        {"host_id": str(host_id)},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Calendar not found")

    row = dict(row)
    row["topics"] = _parse_json_list(row.get("topics"))
    return row


@router.patch(
    "/calendars/me",
    response_model=CalendarRead,
)
async def update_my_calendar(
    data: CalendarUpdate,
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    host_id: UUID = host["id"]

    # 현재 값 조회
    cur = await session.execute(
        text("""
            SELECT id, host_id, topics, description, created_at, updated_at
            FROM calendars
            WHERE host_id = :host_id
        """),
        {"host_id": str(host_id)},
    )
    row = cur.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Calendar not found")

    current_topics = _parse_json_list(row.get("topics"))
    new_topics = data.topics if data.topics is not None else current_topics
    new_description = data.description if data.description is not None else row.get("description")

    topics_json = json.dumps(new_topics)

    updated = await session.execute(
        text("""
            UPDATE calendars
            SET topics = CAST(:topics AS jsonb),
                description = :description,
                updated_at = now()
            WHERE host_id = :host_id
            RETURNING id, host_id, topics, description, created_at, updated_at
        """),
        {
            "topics": topics_json,
            "description": new_description,
            "host_id": str(host_id),
        },
    )
    await session.commit()
    out = updated.mappings().one()
    out = dict(out)
    out["topics"] = _parse_json_list(out.get("topics"))
    return out


# -----------------------
# Host: TimeSlots CRUD
# -----------------------

@router.post(
    "/calendars/me/time-slots",
    response_model=TimeSlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_time_slot(
    data: TimeSlotCreate,
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    """
    호스트가 자신의 캘린더에 반복 시간대를 추가
    """
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    for w in data.weekdays:
        if w < 0 or w > 6:
            raise HTTPException(status_code=400, detail="weekdays must be within 0..6")

    host_id: UUID = host["id"]

    cal = await session.execute(
        text("SELECT id FROM calendars WHERE host_id = :host_id"),
        {"host_id": str(host_id)},
    )
    cal_row = cal.first()
    if not cal_row:
        raise HTTPException(status_code=404, detail="Calendar not found")
    calendar_id = cal_row[0]

    weekdays_json = json.dumps(data.weekdays)

    result = await session.execute(
        text("""
            INSERT INTO time_slots (start_time, end_time, weekdays, calendar_id)
            VALUES (:start_time, :end_time, CAST(:weekdays AS jsonb), :calendar_id)
            RETURNING id, calendar_id, start_time, end_time, weekdays, created_at, updated_at
        """),
        {
            "start_time": data.start_time,
            "end_time": data.end_time,
            "weekdays": weekdays_json,
            "calendar_id": calendar_id,
        },
    )
    await session.commit()
    out = result.mappings().one()
    out = dict(out)
    out["weekdays"] = _parse_json_list(out.get("weekdays"))
    return out


@router.get(
    "/calendars/me/time-slots",
    response_model=list[TimeSlotRead],
)
async def list_my_time_slots(
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    host_id: UUID = host["id"]

    cal = await session.execute(
        text("SELECT id FROM calendars WHERE host_id = :host_id"),
        {"host_id": str(host_id)},
    )
    cal_row = cal.first()
    if not cal_row:
        raise HTTPException(status_code=404, detail="Calendar not found")
    calendar_id = cal_row[0]

    result = await session.execute(
        text("""
            SELECT id, calendar_id, start_time, end_time, weekdays, created_at, updated_at
            FROM time_slots
            WHERE calendar_id = :calendar_id
            ORDER BY id ASC
        """),
        {"calendar_id": calendar_id},
    )
    rows = [dict(r) for r in result.mappings().all()]
    for r in rows:
        r["weekdays"] = _parse_json_list(r.get("weekdays"))
    return rows


@router.delete(
    "/calendars/me/time-slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_time_slot(
    slot_id: int,
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    """
    time_slot 삭제는 '예약(bookings)이 하나도 없을 때만' 허용.
    (FK가 NO ACTION이면 예약이 있으면 DB가 삭제를 막기도 하지만,
     우리는 더 친절한 에러를 주기 위해 선제 체크)
    """
    host_id: UUID = host["id"]

    cal = await session.execute(
        text("SELECT id FROM calendars WHERE host_id = :host_id"),
        {"host_id": str(host_id)},
    )
    cal_row = cal.first()
    if not cal_row:
        raise HTTPException(status_code=404, detail="Calendar not found")
    calendar_id = cal_row[0]

    # 내 캘린더 소유 slot인지 확인
    slot = await session.execute(
        text("""
            SELECT id FROM time_slots
            WHERE id = :slot_id AND calendar_id = :calendar_id
        """),
        {"slot_id": slot_id, "calendar_id": calendar_id},
    )
    if not slot.first():
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    # 예약 존재 여부(예약이 있으면 삭제 금지)
    b = await session.execute(
        text("SELECT 1 FROM bookings WHERE time_slot_id = :slot_id LIMIT 1"),
        {"slot_id": slot_id},
    )
    if b.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TimeSlot has bookings and cannot be deleted",
        )

    await session.execute(
        text("DELETE FROM time_slots WHERE id = :slot_id AND calendar_id = :calendar_id"),
        {"slot_id": slot_id, "calendar_id": calendar_id},
    )
    await session.commit()
    return None


# -----------------------
# Public: Host Calendar & Availability
# -----------------------

@router.get(
    "/calendars/{host_id}",
    response_model=CalendarRead,
)
async def get_host_calendar(
    host_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    게스트가 호스트 캘린더 기본 정보 조회 (topics/description)
    """
    result = await session.execute(
        text("""
            SELECT id, host_id, topics, description, created_at, updated_at
            FROM calendars
            WHERE host_id = :host_id
        """),
        {"host_id": str(host_id)},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Calendar not found")

    row = dict(row)
    row["topics"] = _parse_json_list(row.get("topics"))
    return row


@router.get(
    "/calendars/{host_id}/availability",
    response_model=AvailabilityResponse,
)
async def get_availability(
    host_id: UUID,
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    """
    호스트의 반복 time_slots - (이미 잡힌 bookings) 를 빼서
    날짜별 예약 가능 슬롯을 계산한다.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    cal = await session.execute(
        text("SELECT id FROM calendars WHERE host_id = :host_id"),
        {"host_id": str(host_id)},
    )
    cal_row = cal.first()
    if not cal_row:
        raise HTTPException(status_code=404, detail="Calendar not found")
    calendar_id = cal_row[0]

    # 1) 모든 time_slots
    slots_res = await session.execute(
        text("""
            SELECT id, start_time, end_time, weekdays
            FROM time_slots
            WHERE calendar_id = :calendar_id
            ORDER BY id ASC
        """),
        {"calendar_id": calendar_id},
    )
    slots = []
    for r in slots_res.mappings().all():
        rr = dict(r)
        rr["weekdays"] = _parse_json_list(rr.get("weekdays"))
        slots.append(rr)

    # 2) 기간 내 예약(취소는 가용으로 보기 위해 제외)
    #    status != 'CANCELLED' 인 예약은 "차단"
    booked_res = await session.execute(
        text("""
            SELECT b.time_slot_id, b."when"
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.time_slot_id
            WHERE ts.calendar_id = :calendar_id
              AND b."when" >= :start
              AND b."when" <= :end
              AND b.status <> 'CANCELLED'
        """),
        {"calendar_id": calendar_id, "start": start, "end": end},
    )
    booked_set = {(row[0], row[1]) for row in booked_res.all()}  # (time_slot_id, when)

    days_out = []
    for d in _date_range_inclusive(start, end):
        wd = _weekday_0_mon(d)
        day_slots = []

        for s in slots:
            if wd not in s["weekdays"]:
                continue
            if (s["id"], d) in booked_set:
                continue
            day_slots.append(
                AvailabilitySlot(
                    time_slot_id=s["id"],
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                )
            )

        days_out.append(AvailabilityDay(date=d, slots=day_slots))

    return AvailabilityResponse(host_id=host_id, start=start, end=end, days=days_out)


# -----------------------
# Bookings (Guest + Host)
# -----------------------

@router.post(
    "/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    data: BookingCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """
    게스트 예약 생성
    - time_slot 요일 체크
    - unique(when, time_slot_id)로 더블부킹 방지
    """
    guest_id: UUID = user["id"]

    # time_slot 존재 확인 + weekdays 읽기
    ts_res = await session.execute(
        text("""
            SELECT id, calendar_id, weekdays
            FROM time_slots
            WHERE id = :time_slot_id
        """),
        {"time_slot_id": data.time_slot_id},
    )
    ts = ts_res.mappings().first()
    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    weekdays = _parse_json_list(ts.get("weekdays"))
    if _weekday_0_mon(data.when) not in weekdays:
        raise HTTPException(status_code=400, detail="Selected date is not available for this time slot")

    try:
        result = await session.execute(
            text("""
                INSERT INTO bookings ("when", topic, status, description, time_slot_id, guest_id)
                VALUES (:when, :topic, 'CONFIRMED', :description, :time_slot_id, :guest_id)
                RETURNING id, "when", topic, status, description, time_slot_id, guest_id, created_at, updated_at
            """),
            {
                "when": data.when,
                "topic": data.topic,
                "description": data.description,
                "time_slot_id": data.time_slot_id,
                "guest_id": str(guest_id),
            },
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # unique(when, time_slot_id) 충돌일 확률이 가장 큼
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked for the selected date",
        )

    return result.mappings().one()


@router.get(
    "/bookings/me",
    response_model=list[BookingRead],
)
async def list_my_bookings(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    guest_id: UUID = user["id"]

    result = await session.execute(
        text("""
            SELECT id, "when", topic, status, description, time_slot_id, guest_id, created_at, updated_at
            FROM bookings
            WHERE guest_id = :guest_id
            ORDER BY "when" DESC, id DESC
        """),
        {"guest_id": str(guest_id)},
    )
    return [r for r in result.mappings().all()]


@router.get(
    "/calendars/me/bookings",
    response_model=list[BookingRead],
)
async def list_my_calendar_bookings(
    start: date = Query(...),
    end: date = Query(...),
    session: AsyncSession = Depends(get_session),
    host=Depends(get_current_host),
):
    """
    호스트가 자기 캘린더에 들어온 예약을 기간으로 조회
    """
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    host_id: UUID = host["id"]

    cal = await session.execute(
        text("SELECT id FROM calendars WHERE host_id = :host_id"),
        {"host_id": str(host_id)},
    )
    cal_row = cal.first()
    if not cal_row:
        raise HTTPException(status_code=404, detail="Calendar not found")
    calendar_id = cal_row[0]

    result = await session.execute(
        text("""
            SELECT b.id, b."when", b.topic, b.status, b.description, b.time_slot_id, b.guest_id, b.created_at, b.updated_at
            FROM bookings b
            JOIN time_slots ts ON ts.id = b.time_slot_id
            WHERE ts.calendar_id = :calendar_id
              AND b."when" >= :start
              AND b."when" <= :end
            ORDER BY b."when" DESC, b.id DESC
        """),
        {"calendar_id": calendar_id, "start": start, "end": end},
    )
    return [r for r in result.mappings().all()]


@router.patch(
    "/bookings/{booking_id}/cancel",
    response_model=BookingCancelResponse,
)
async def cancel_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """
    예약 취소: row 삭제가 아니라 status 변경(운영 정석)
    - 예약자(guest) 또는 해당 호스트가 취소 가능하도록 확장 가능
    - 지금은 '예약자 본인' 취소를 기본으로 구현
    """
    user_id: UUID = user["id"]

    # 예약이 존재하고, 내가 guest인지 확인
    res = await session.execute(
        text("""
            SELECT id, guest_id, status
            FROM bookings
            WHERE id = :booking_id
        """),
        {"booking_id": booking_id},
    )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")

    if str(row["guest_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Only the guest can cancel this booking")

    if row["status"] == "CANCELLED":
        # 멱등성: 이미 취소된 예약은 그대로 반환
        res2 = await session.execute(
            text("""SELECT id, status, updated_at FROM bookings WHERE id = :booking_id"""),
            {"booking_id": booking_id},
        )
        return res2.mappings().one()

    updated = await session.execute(
        text("""
            UPDATE bookings
            SET status = 'CANCELLED',
                updated_at = now()
            WHERE id = :booking_id
            RETURNING id, status, updated_at
        """),
        {"booking_id": booking_id},
    )
    await session.commit()
    return updated.mappings().one()
