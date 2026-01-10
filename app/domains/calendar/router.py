from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.calendar.models import Booking, Calendar, TimeSlot
from app.domains.calendar.schemas import (
    AvailabilityDay,
    AvailabilityResponse,
    AvailabilitySlot,
    BookingCancelResponse,
    BookingCreate,
    BookingRead,
    CalendarCreate,
    CalendarRead,
    CalendarUpdate,
    TimeSlotCreate,
    TimeSlotRead,
    TimeSlotUpdate,
)

router = APIRouter()
cal_router = APIRouter(prefix="/calendars", tags=["Calendar"])
bk_router = APIRouter(prefix="/bookings", tags=["Booking"])


# Helpers (필수만 최소)
def _date_range_inclusive(start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


async def _get_calendar_id_by_host(session: AsyncSession, host_id: UUID) -> int:
    result = await session.execute(select(Calendar.id).where(Calendar.host_id == host_id))
    cal_id = result.scalar_one_or_none()
    if cal_id is None:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return cal_id

# NEW: 409(예약 충돌) 응답을 운영용으로 통일 (프론트가 파싱하기 쉬움)
def _booking_conflict_detail(*, time_slot_id: int, when: date, error: str) -> dict:
    return {
        "error": error,  # e.g. SLOT_ALREADY_BOOKED / BOOKING_CONFLICT
        "message": "이미 예약된 시간대입니다. 최신 일정으로 갱신 후 다시 선택해주세요."
        if error == "SLOT_ALREADY_BOOKED"
        else "예약 충돌이 발생했습니다. 최신 일정으로 갱신 후 다시 시도해주세요.",
        "hint": "REFETCH_AVAILABILITY",  # 프론트: availability 재조회 트리거
        "time_slot_id": time_slot_id,
        "when": when.isoformat(),
    }

def _raise_slot_already_booked(*, time_slot_id: int, when: date) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_booking_conflict_detail(time_slot_id=time_slot_id, when=when, error="SLOT_ALREADY_BOOKED"),
    )

def _raise_booking_conflict(*, time_slot_id: int, when: date) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_booking_conflict_detail(time_slot_id=time_slot_id, when=when, error="BOOKING_CONFLICT"),
    )


# Host: My Calendar
@cal_router.post(
    "/me",
    response_model=CalendarRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_calendar(
    data: CalendarCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))

    # 호스트당 1개만(UNIQUE)
    exists = await session.execute(select(Calendar).where(Calendar.host_id == host_id))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Calendar already exists for this host")

    calendar = Calendar(
        host_id=host_id,
        topics=data.topics,
        description=data.description,
    )
    session.add(calendar)
    await session.commit()
    await session.refresh(calendar)
    return calendar


@cal_router.get("/me", response_model=CalendarRead)
async def get_my_calendar(
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))

    result = await session.execute(select(Calendar).where(Calendar.host_id == host_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@cal_router.patch("/me", response_model=CalendarRead)
async def update_my_calendar(
    data: CalendarUpdate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))

    result = await session.execute(select(Calendar).where(Calendar.host_id == host_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    payload = data.model_dump(exclude_unset=True)
    if "topics" in payload:
        calendar.topics = payload["topics"]
    if "description" in payload:
        calendar.description = payload["description"]

    session.add(calendar)
    await session.commit()
    await session.refresh(calendar)
    return calendar


# Host: TimeSlots CRUD
@cal_router.post(
    "/me/time-slots",
    response_model=TimeSlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_time_slot(
    data: TimeSlotCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    if any((w < 0 or w > 6) for w in data.weekdays):
        raise HTTPException(status_code=400, detail="weekdays must be within 0..6")

    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    ts = TimeSlot(
        calendar_id=calendar_id,
        start_time=data.start_time,
        end_time=data.end_time,
        weekdays=data.weekdays,
    )
    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


@cal_router.get("/me/time-slots", response_model=list[TimeSlotRead])
async def list_my_time_slots(
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    result = await session.execute(
        select(TimeSlot)
        .where(TimeSlot.calendar_id == calendar_id)
        .order_by(TimeSlot.id.asc())
    )
    return result.scalars().all()


@cal_router.patch("/me/time-slots/{slot_id}", response_model=TimeSlotRead)
async def update_time_slot(
    slot_id: int,
    data: TimeSlotUpdate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    result = await session.execute(
        select(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.calendar_id == calendar_id)
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    payload = data.model_dump(exclude_unset=True)

    if "start_time" in payload:
        ts.start_time = payload["start_time"]
    if "end_time" in payload:
        ts.end_time = payload["end_time"]
    if "weekdays" in payload:
        if any((w < 0 or w > 6) for w in (payload["weekdays"] or [])):
            raise HTTPException(status_code=400, detail="weekdays must be within 0..6")
        ts.weekdays = payload["weekdays"]

    if ts.end_time <= ts.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


@cal_router.delete("/me/time-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_slot(
    slot_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    """
    TimeSlot 삭제는 '예약이 하나도 없을 때만' 허용
    - FK가 NO ACTION이어도, 더 친절한 409를 주기 위해 선제 체크
    """
    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    result = await session.execute(
        select(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.calendar_id == calendar_id)
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    booked = await session.execute(
        select(Booking.id).where(Booking.time_slot_id == slot_id).limit(1)
    )
    if booked.first():
        raise HTTPException(status_code=409, detail="TimeSlot has bookings and cannot be deleted")

    await session.delete(ts)
    await session.commit()
    return None


# Public: Host Calendar & Availability
@cal_router.get("/{host_id}", response_model=CalendarRead)
async def get_host_calendar(
    host_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Calendar).where(Calendar.host_id == host_id))
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@cal_router.get("/{host_id}/availability", response_model=AvailabilityResponse)
async def get_availability(
    host_id: UUID,
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    # 운영 안전장치(너무 큰 기간 조회 방지) - 필요없으면 지워도 됨
    if (end - start).days > 90:
        raise HTTPException(status_code=400, detail="range is too large (max 90 days)")

    # 캘린더 존재 확인
    result = await session.execute(select(Calendar.id).where(Calendar.host_id == host_id))
    calendar_id = result.scalar_one_or_none()
    if calendar_id is None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    # 1) 해당 캘린더의 모든 time_slots
    slots_res = await session.execute(
        select(TimeSlot).where(TimeSlot.calendar_id == calendar_id).order_by(TimeSlot.id.asc())
    )
    slots = slots_res.scalars().all()

    # 2) 기간 내 예약(취소 제외) -> (time_slot_id, when) set
    booked_res = await session.execute(
        select(Booking.time_slot_id, Booking.when)
        .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
        .where(
            TimeSlot.calendar_id == calendar_id,
            Booking.when >= start,
            Booking.when <= end,
            Booking.status != "CANCELLED",
        )
    )
    booked_set = {(row[0], row[1]) for row in booked_res.all()}

    days_out: list[AvailabilityDay] = []
    for d in _date_range_inclusive(start, end):
        wd = d.weekday()  # 월0~일6
        day_slots: list[AvailabilitySlot] = []

        for s in slots:
            if wd not in (s.weekdays or []):
                continue
            if (s.id, d) in booked_set:
                continue
            day_slots.append(
                AvailabilitySlot(
                    time_slot_id=s.id,
                    start_time=s.start_time,
                    end_time=s.end_time,
                )
            )

        days_out.append(AvailabilityDay(date=d, slots=day_slots))

    return AvailabilityResponse(host_id=host_id, start=start, end=end, days=days_out)


# Bookings (Guest + Host)
@bk_router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    guest_id = UUID(str(user.id))

    # time_slot 존재 확인 + weekdays 체크
    ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == data.time_slot_id))
    ts = ts_res.scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    if data.when.weekday() not in (ts.weekdays or []):
        raise HTTPException(status_code=400, detail="Selected date is not available for this time slot")

    # "취소가 아닌" 예약만 중복으로 막는다
    existing = await session.execute(
        select(Booking.id).where(
            Booking.time_slot_id == data.time_slot_id,
            Booking.when == data.when,
            Booking.status != "CANCELLED",
        )
    )
    if existing.scalar_one_or_none():
        # 운영 친화적 409 (프론트가 이걸 보고 안내+재조회)
        _raise_slot_already_booked(time_slot_id=data.time_slot_id, when=data.when)

    booking = Booking(
        when=data.when,
        topic=data.topic,
        description=data.description,
        time_slot_id=data.time_slot_id,
        guest_id=guest_id,
        status="CONFIRMED",
    )
    session.add(booking)

    try:
        await session.commit()
        await session.refresh(booking)
        return booking

    except IntegrityError:
        # 레이스 컨디션(동시 예약) 최종 방어
        await session.rollback()

        # 커밋 실패 후 DB를 다시 확인해서 "진짜 이미 예약"인지 판단
        again = await session.execute(
            select(Booking.id).where(
                Booking.time_slot_id == data.time_slot_id,
                Booking.when == data.when,
                Booking.status != "CANCELLED",
            )
        )
        if again.scalar_one_or_none():
            _raise_slot_already_booked(time_slot_id=data.time_slot_id, when=data.when)

        # active booking이 없으면 정책/인덱스 불일치 등 "충돌"로 처리
        _raise_booking_conflict(time_slot_id=data.time_slot_id, when=data.when)


@bk_router.get("/me", response_model=list[BookingRead])
async def list_my_bookings(
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    guest_id = UUID(str(user.id))
    result = await session.execute(
        select(Booking).where(Booking.guest_id == guest_id).order_by(Booking.when.desc(), Booking.id.desc())
    )
    return result.scalars().all()


@cal_router.get("/me/bookings", response_model=list[BookingRead])
async def list_my_calendar_bookings(
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    stmt = (
        select(Booking)
        .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
        .where(
            TimeSlot.calendar_id == calendar_id,
            Booking.when >= start,
            Booking.when <= end,
        )
        .order_by(Booking.when.desc(), Booking.id.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@bk_router.patch("/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_guest(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """
    게스트(예약자) 취소
    - row 삭제가 아니라 status 변경(운영 정석)
    """
    user_id = UUID(str(user.id))

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.guest_id != user_id:
        raise HTTPException(status_code=403, detail="Only the guest can cancel this booking")

    if booking.status == "CANCELLED":
        return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)

    booking.status = "CANCELLED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


@cal_router.patch("/me/bookings/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "MANAGER", "ADMIN"})),
):
    """
    호스트(코치) 취소
    - 본인 캘린더의 예약만 취소 가능
    """
    host_id = UUID(str(host.id))
    calendar_id = await _get_calendar_id_by_host(session, host_id)

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
    ts = ts_res.scalar_one_or_none()
    if not ts or ts.calendar_id != calendar_id:
        raise HTTPException(status_code=403, detail="You can cancel bookings only in your calendar")

    if booking.status == "CANCELLED":
        return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)

    booking.status = "CANCELLED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


# main.py에서 include_router(calendar_router)로 한 번만 붙일 수 있게 export
router.include_router(cal_router)
router.include_router(bk_router)
