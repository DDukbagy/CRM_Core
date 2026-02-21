from __future__ import annotations

from datetime import date, timedelta, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from icalendar import Calendar as ICal, Event as ICalEvent

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.calendar.models import Booking, Calendar, TimeSlot, BookingType
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
    TimeSlotWeekdaysPatch,
    BookingCancelRequest,
)

router = APIRouter()
cal_router = APIRouter(prefix="/calendars", tags=["Calendar"])
bk_router = APIRouter(prefix="/bookings", tags=["Booking"])


# --- Helpers ---
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


# 409(예약 충돌) 응답
def _booking_conflict_detail(*, time_slot_id: int, when: date, error: str) -> dict:
    return {
        "error": error,  # e.g. SLOT_ALREADY_BOOKED / BOOKING_CONFLICT
        "message": "이미 예약된 시간대입니다. 최신 일정으로 갱신 후 다시 선택해주세요."
        if error == "SLOT_ALREADY_BOOKED"
        else "예약 충돌이 발생했습니다. 최신 일정으로 갱신 후 다시 시도해주세요.",
        "hint": "REFETCH_AVAILABILITY",
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


# --- Host: My Calendar ---
@cal_router.post(
    "/me",
    response_model=CalendarRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_calendar(
    data: CalendarCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
):
    host_id = UUID(str(host.id))

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
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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


# --- Host: TimeSlots CRUD ---
@cal_router.post(
    "/me/time-slots",
    response_model=TimeSlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_time_slot(
    data: TimeSlotCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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
        #   - schema에 is_active가 들어오면 여기서 세팅
    )
    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


@cal_router.get("/me/time-slots", response_model=list[TimeSlotRead])
async def list_my_time_slots(
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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

    # TimeSlot.is_active 업데이트 지원
    if "is_active" in payload:
        if hasattr(ts, "is_active"):
            ts.is_active = payload["is_active"]

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
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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


# --- Public: Host Calendar & Availability ---
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

    # 너무 큰 기간 조회 방지
    if (end - start).days > 90:
        raise HTTPException(status_code=400, detail="range is too large (max 90 days)")

    # 캘린더 존재 확인
    result = await session.execute(select(Calendar.id).where(Calendar.host_id == host_id))
    calendar_id = result.scalar_one_or_none()
    if calendar_id is None:
        raise HTTPException(status_code=404, detail="Calendar not found")

    # 해당 캘린더의 모든 time_slots
    slots_res = await session.execute(
        select(TimeSlot).where(TimeSlot.calendar_id == calendar_id, TimeSlot.is_active == True,).order_by(TimeSlot.id.asc())
    )
    slots = slots_res.scalars().all()

    # 기간 내 예약(취소 제외) 조회
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


# --- Bookings (Guest + Host) ---
@bk_router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """
    - LESSON: 고객이 생성하면 status=REQUESTED (확정은 강사)
    - HOLIDAY: 강사(호스트)만 생성 가능, status=CONFIRMED
    """
    guest_id = UUID(str(user.id))
    user_role = ((getattr(user, "role", None) or "CUSTOMER").strip()).upper()

    # TimeSlot 존재 확인
    ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == data.time_slot_id))
    ts = ts_res.scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")
    if not ts.is_active:
        raise HTTPException(status_code=400, detail="TimeSlot is inactive")

    if data.when.weekday() not in (ts.weekdays or []):
        raise HTTPException(status_code=400, detail="Selected date is not available for this time slot")

    # TimeSlot -> Calendar -> Host 확인
    cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
    calendar = cal_res.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    host_id = UUID(str(calendar.host_id))

    # 타입별 권한/상태 고정
    if data.type == BookingType.HOLIDAY:
        # 휴무는 해당 TimeSlot의 주인(Host)만 등록
        if host_id != guest_id:
            raise HTTPException(status_code=403, detail="Only the host can schedule a HOLIDAY")
        # 휴무는 생성 즉시 확정
        initial_status = "CONFIRMED"
    else:
        # LESSON
        # 고객/관리자만 요청 생성 가능 (강사 - 확정권한만)
        if user_role not in {"CUSTOMER", "ADMIN"}:
            raise HTTPException(status_code=403, detail="Only customer can request a LESSON booking")
        initial_status = "REQUESTED"

    # 중복 예약 확인
    existing = await session.execute(
        select(Booking.id).where(
            Booking.time_slot_id == data.time_slot_id,
            Booking.when == data.when,
            Booking.status != "CANCELLED",
        )
    )
    if existing.scalar_one_or_none():
        _raise_slot_already_booked(time_slot_id=data.time_slot_id, when=data.when)

    booking = Booking(
        when=data.when,
        topic=data.topic,
        description=data.description,
        time_slot_id=data.time_slot_id,
        guest_id=guest_id,
        status=initial_status,
        type=data.type,  # LESSON or HOLIDAY
    )
    session.add(booking)

    try:
        await session.commit()
        await session.refresh(booking)
        return booking

    except IntegrityError:
        await session.rollback()
        # 동시성 처리
        again = await session.execute(
            select(Booking.id).where(
                Booking.time_slot_id == data.time_slot_id,
                Booking.when == data.when,
                Booking.status != "CANCELLED",
            )
        )
        if again.scalar_one_or_none():
            _raise_slot_already_booked(time_slot_id=data.time_slot_id, when=data.when)

        _raise_booking_conflict(time_slot_id=data.time_slot_id, when=data.when)


@bk_router.get("/me", response_model=list[BookingRead])
async def list_my_bookings(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
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
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
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


@cal_router.patch("/me/bookings/{booking_id}/confirm", response_model=BookingRead)
async def confirm_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    확정 : REQUESTED -> CONFIRMED
    - (ADMIN은 전체 확정 허용)
    """
    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # HOLIDAY는 확정 대상 X
    if booking.type == BookingType.HOLIDAY:
        raise HTTPException(status_code=400, detail="HOLIDAY booking does not require confirmation")

    if booking.status == "CONFIRMED":
        return booking
    if booking.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Cancelled booking cannot be confirmed")
    if booking.status != "REQUESTED":
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CONFIRMED")

    # ADMIN - 전체 허용, INSTRUCTOR - 내 캘린더 소유 예약만
    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")

        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can confirm bookings only in your calendar")

    booking.status = "CONFIRMED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


@cal_router.patch("/me/bookings/{booking_id}/decline", response_model=BookingRead)
async def decline_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    거절 : REQUESTED -> CANCELLED (슬롯 다시 열림)
    - (ADMIN은 전체 거절 허용)
    """
    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.type == BookingType.HOLIDAY:
        raise HTTPException(status_code=400, detail="HOLIDAY booking cannot be declined")

    if booking.status == "CANCELLED":
        return booking
    if booking.status != "REQUESTED":
        # - CONFIRMED 이후는 cancel로 처리
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")

    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")

        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can decline bookings only in your calendar")

    booking.status = "CANCELLED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


@bk_router.patch("/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_guest(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """
    게스트(예약자) 취소
    - row 삭제 X, status 변경
    - 고객 cancel: REQUESTED(요청 철회) / CONFIRMED(확정 취소) 모두 허용
      (거절은 decline로만 처리)
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

    # COMPLETED는 취소 불가
    if booking.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Completed booking cannot be cancelled")

    # 고객 cancel 허용 상태 제한
    if booking.status not in {"REQUESTED", "CONFIRMED"}:
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")

    booking.status = "CANCELLED"

    # cancel_reason 저장
    if body is not None and getattr(body, "reason", None):
        if hasattr(booking, "cancel_reason"):
            booking.cancel_reason = body.reason

    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


@cal_router.patch("/me/bookings/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_host(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
):
    """
    강사 취소
    - 본인 캘린더의 예약만 취소 가능
    - 강사 cancel: CONFIRMED -> CANCELLED (확정 취소)
    - REQUESTED 상태는 decline(거절)로만 처리
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

    # COMPLETED는 취소 불가
    if booking.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Completed booking cannot be cancelled")

    # 강사 취소는 CONFIRMED에서만
    # - HOLIDAY는 host가 만든 확정 블록이므로 CONFIRMED 취소 허용
    if booking.type != BookingType.HOLIDAY:
        if booking.status == "REQUESTED":
            raise HTTPException(status_code=400, detail="Requested booking should be declined, not cancelled")
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")

    booking.status = "CANCELLED"

    # cancel_reason 저장
    if body is not None and getattr(body, "reason", None):
        if hasattr(booking, "cancel_reason"):
            booking.cancel_reason = body.reason

    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


# 스마트폰 캘린더용 .ics 파일 다운로드
@bk_router.get("/{booking_id}/download", summary="스마트폰 캘린더 연동 (.ics 다운로드)")
async def download_booking_ics(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    # 예약 정보 조회
    stmt = select(Booking).where(Booking.id == booking_id)
    result = await session.execute(stmt)
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # TimeSlot 정보 (시간 확인용)
    ts_result = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
    ts = ts_result.scalar_one_or_none()

    if not ts:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    # ICS 파일 생성
    cal = ICal()
    event = ICalEvent()

    event.add('summary', f"[CRM 예약] {booking.topic}")
    event.add('description', booking.description or "CRM 앱에서 생성된 예약입니다.")

    start_dt = datetime.combine(booking.when, ts.start_time)
    end_dt = datetime.combine(booking.when, ts.end_time)

    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)
    event.add('dtstamp', datetime.now())

    cal.add_component(event)

    filename = f"booking_{booking_id}.ics"
    return Response(
        content=cal.to_ical(),
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.patch("/calendars/me/time-slots/{time_slot_id}/weekdays")
async def patch_my_time_slot_weekdays(
    time_slot_id: int,
    body: TimeSlotWeekdaysPatch,
    session: AsyncSession = Depends(get_session),
    me=Depends(get_current_user),
):
    """
    내 캘린더(= calendars.host_id == me.id)에 속한 time_slot만 수정 가능
    time_slots.weekdays는 jsonb(list[int])로 저장
    """
    stmt = (
        select(TimeSlot)
        .join(Calendar, Calendar.id == TimeSlot.calendar_id)
        .where(TimeSlot.id == time_slot_id, Calendar.host_id == me.id)
    )
    slot = await session.scalar(stmt)
    if not slot:
        raise HTTPException(status_code=403, detail="You can update time slots only in your calendar")

    slot.weekdays = body.weekdays
    await session.commit()
    await session.refresh(slot)

    return {
        "id": slot.id,
        "calendar_id": slot.calendar_id,
        "weekdays": slot.weekdays,
    }


router.include_router(cal_router)
router.include_router(bk_router)