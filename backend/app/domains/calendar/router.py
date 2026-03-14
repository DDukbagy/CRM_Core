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
from app.core.push import send_push
from app.db.session import get_session
from app.domains.calendar.models import Booking, Calendar, TimeSlot, BookingType
from app.domains.users.models import User
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
    BookingConfirmRequest,
    BookingUpdateRequest,
)

router = APIRouter()
cal_router = APIRouter(prefix="/calendars", tags=["Calendar"])
bk_router = APIRouter(prefix="/bookings", tags=["Booking"])


# --- Helpers ---
async def _get_guest_push_token(session, guest_id: UUID) -> str | None:
    u = await session.get(User, guest_id)
    return getattr(u, "push_token", None) if u else None


async def _get_host_push_token(session, booking: Booking) -> str | None:
    ts = await session.get(TimeSlot, booking.time_slot_id)
    if not ts:
        return None
    cal = await session.get(Calendar, ts.calendar_id)
    if not cal:
        return None
    u = await session.get(User, cal.host_id)
    return getattr(u, "push_token", None) if u else None


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

    # 호스트 정보 조회 (정기 휴무 요일 확인)
    host_res = await session.execute(select(User).where(User.id == host_id))
    host = host_res.scalar_one_or_none()
    recurring_off: set[int] = set(host.recurring_off_days or []) if host else set()

    # 해당 캘린더의 모든 time_slots
    slots_res = await session.execute(
        select(TimeSlot).where(TimeSlot.calendar_id == calendar_id, TimeSlot.is_active == True,).order_by(TimeSlot.id.asc())
    )
    slots = slots_res.scalars().all()

    # 기간 내 예약(취소 제외) 조회 — slot_id + 시간 범위 양쪽으로 체크
    booked_res = await session.execute(
        select(Booking.time_slot_id, Booking.when, TimeSlot.start_time, TimeSlot.end_time, Booking.type)
        .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
        .where(
            TimeSlot.calendar_id == calendar_id,
            Booking.when >= start,
            Booking.when <= end,
            Booking.status != "CANCELLED",
        )
    )
    booked_rows = booked_res.all()
    # HOLIDAY 예약이 있는 날짜 — 해당 날의 모든 슬롯 차단
    holiday_dates: set = {row[1] for row in booked_rows if row[4] == "HOLIDAY"}
    # WORK_OVERRIDE: 날짜 → 활성화된 slot_id 집합 (특정 시간만 열기)
    work_override_by_date: dict = {}
    for row in booked_rows:
        if row[4] == "WORK_OVERRIDE":
            work_override_by_date.setdefault(row[1], set()).add(row[0])
    # (slot_id, date) 집합 — 직접 예약된 슬롯
    booked_slot_date: set[tuple] = {(row[0], row[1]) for row in booked_rows if row[4] not in ("HOLIDAY", "WORK_OVERRIDE")}
    # (start_time, end_time, date) 집합 — 같은 시간대가 중복 슬롯일 때 통째로 막기
    booked_time_date: set[tuple] = {(row[2], row[3], row[1]) for row in booked_rows if row[4] not in ("HOLIDAY", "WORK_OVERRIDE")}

    days_out: list[AvailabilityDay] = []
    for d in _date_range_inclusive(start, end):
        wd = d.weekday()  # 월0~일6

        # 정기 휴무 요일이거나 HOLIDAY 예약이 있는 날
        if wd in recurring_off or d in holiday_dates:
            override_slot_ids = work_override_by_date.get(d)
            if override_slot_ids:
                # 특정 시간만 활성화된 경우 — 해당 슬롯만 반환
                partial: list[AvailabilitySlot] = []
                seen_partial: set[tuple] = set()
                for s in slots:
                    if s.id not in override_slot_ids:
                        continue
                    tk = (s.start_time, s.end_time)
                    if tk in seen_partial:
                        continue
                    seen_partial.add(tk)
                    partial.append(AvailabilitySlot(time_slot_id=s.id, start_time=s.start_time, end_time=s.end_time))
                days_out.append(AvailabilityDay(date=d, slots=partial))
            else:
                days_out.append(AvailabilityDay(date=d, slots=[]))
            continue

        day_slots: list[AvailabilitySlot] = []
        seen_times: set[tuple] = set()  # 같은 시간대 중복 제거

        for s in slots:
            if wd not in (s.weekdays or []):
                continue
            # 이 슬롯 자체가 예약됨
            if (s.id, d) in booked_slot_date:
                continue
            # 동일 시간대의 다른 슬롯이 예약됨
            if (s.start_time, s.end_time, d) in booked_time_date:
                continue
            # 중복 시간대 제거 (같은 start/end 는 하나만 노출)
            time_key = (s.start_time, s.end_time)
            if time_key in seen_times:
                continue
            seen_times.add(time_key)
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
        initial_status = "CONFIRMED"
    elif data.type == BookingType.WORK_OVERRIDE:
        # 정기 휴무 요일 영업일 전환도 호스트(강사)만 가능
        if host_id != guest_id:
            raise HTTPException(status_code=403, detail="Only the host can create a WORK_OVERRIDE")
        initial_status = "CONFIRMED"
    else:
        # LESSON: 고객/관리자만 요청 생성 가능
        if user_role not in {"CUSTOMER", "ADMIN"}:
            raise HTTPException(status_code=403, detail="Only customer can request a LESSON booking")
        initial_status = "REQUESTED"

    # 중복 예약 확인 (타입별로 분리 — HOLIDAY+WORK_OVERRIDE는 같은 슬롯에 공존 가능)
    existing = await session.execute(
        select(Booking.id).where(
            Booking.time_slot_id == data.time_slot_id,
            Booking.when == data.when,
            Booking.status != "CANCELLED",
            Booking.type == data.type,
        )
    )
    if existing.scalar_one_or_none():
        _raise_slot_already_booked(time_slot_id=data.time_slot_id, when=data.when)

    # 멤버십 연결 시 유효성 검증
    membership_id_to_use = None
    if data.membership_id and data.type == BookingType.LESSON:
        from app.domains.membership.models import Membership as MembershipModel
        mem_res = await session.execute(
            select(MembershipModel).where(MembershipModel.id == data.membership_id)
        )
        membership = mem_res.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
        if membership.customer_id != guest_id:
            raise HTTPException(status_code=403, detail="Membership does not belong to you")
        if not membership.is_active:
            raise HTTPException(status_code=400, detail="수강권이 비활성 상태입니다.")
        if membership.type == "TIMES" and (membership.remaining_count or 0) <= 0:
            raise HTTPException(status_code=400, detail="잔여 횟수가 없습니다.")
        from datetime import date as date_type
        if membership.type == "PERIOD" and membership.expires_at and membership.expires_at < date_type.today():
            raise HTTPException(status_code=400, detail="수강권이 만료되었습니다.")
        membership_id_to_use = data.membership_id

    booking = Booking(
        when=data.when,
        topic=data.topic,
        description=data.description,
        membership_id=membership_id_to_use,
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
                Booking.type == data.type,
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
    body: BookingConfirmRequest | None = None,
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
    if body and body.topic:
        booking.topic = body.topic
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
    await send_push(token, "예약 확정", f"{booking.topic} ({booking.when}) 예약이 확정되었습니다.")
    return booking


@cal_router.patch("/me/bookings/{booking_id}/decline", response_model=BookingRead)
async def decline_booking_as_host(
    booking_id: int,
    body: BookingCancelRequest | None = None,
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
    if body is not None and getattr(body, "reason", None):
        if hasattr(booking, "cancel_reason"):
            booking.cancel_reason = body.reason
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
    await send_push(token, "예약 신청 거절", f"{booking.topic} ({booking.when}) 예약 신청이 거절되었습니다.")
    return booking


@bk_router.patch("/{booking_id}", response_model=BookingRead)
async def update_booking_as_guest(
    booking_id: int,
    body: BookingUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER", "ADMIN"})),
):
    """REQUESTED 상태인 예약의 주제/메모를 수정합니다."""
    user_id = UUID(str(user.id))

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.guest_id != user_id:
        raise HTTPException(status_code=403, detail="Only the guest can modify this booking")

    if booking.status != "REQUESTED":
        raise HTTPException(status_code=400, detail="Only REQUESTED bookings can be modified")

    if body.topic is not None:
        booking.topic = body.topic
    if "description" in body.model_fields_set:
        booking.description = body.description

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
    - REQUESTED는 /withdraw(요청 철회)로 처리 (개념 분리)
    - cancel은 CONFIRMED만 허용
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
    # - REQUESTED는 withdraw(요청 철회)로 처리
    if booking.status == "REQUESTED":
        raise HTTPException(status_code=400, detail="Requested booking should be withdrawn, not cancelled")
    if booking.status == "CANCEL_REQUESTED":
        return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)
    if booking.status != "CONFIRMED":
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCEL_REQUESTED")

    # 고객 취소 신청 → 강사 승인 대기 상태로 전환
    booking.status = "CANCEL_REQUESTED"

    # cancel_reason 저장
    if body is not None and getattr(body, "reason", None):
        if hasattr(booking, "cancel_reason"):
            booking.cancel_reason = body.reason

    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    token = await _get_host_push_token(session, booking)
    guest = await session.get(User, UUID(str(booking.guest_id)))
    guest_name = guest.display_name if guest else "고객"
    await send_push(token, "취소 신청", f"{guest_name}님이 {booking.topic} ({booking.when}) 취소를 신청했습니다.")
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


@bk_router.patch("/{booking_id}/withdraw", response_model=BookingCancelResponse)
async def withdraw_booking_as_guest(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """
    게스트(예약자) 요청 철회
    - row 삭제 X, status 변경
    - REQUESTED 상태에서만 허용
    """
    user_id = UUID(str(user.id))

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.guest_id != user_id:
        raise HTTPException(status_code=403, detail="Only the guest can withdraw this booking")

    if booking.status == "CANCELLED":
        return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)

    # COMPLETED는 철회 불가
    if booking.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Completed booking cannot be withdrawn")

    # 요청 철회는 REQUESTED에서만
    if booking.status != "REQUESTED":
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")

    booking.status = "CANCELLED"

    # cancel_reason 저장(요청철회 사유도 같은 컬럼 사용)
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
    # - HOLIDAY/WORK_OVERRIDE는 host가 만든 확정 블록이므로 CONFIRMED 취소 허용
    if booking.type not in (BookingType.HOLIDAY, BookingType.WORK_OVERRIDE):
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
    if booking.type not in (BookingType.HOLIDAY, BookingType.WORK_OVERRIDE):
        token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
        await send_push(token, "예약 취소", f"{booking.topic} ({booking.when}) 예약이 취소되었습니다.")
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


@cal_router.patch("/me/bookings/{booking_id}/complete", response_model=BookingRead)
async def complete_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    출석 완료 처리: CONFIRMED -> COMPLETED
    - 멤버십(TIMES 타입) 연결된 경우 remaining_count 자동 차감
    """
    from app.domains.membership.models import Membership as MembershipModel

    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # 강사는 본인 캘린더 예약만
    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can complete bookings only in your calendar")

    if booking.status == "COMPLETED":
        return booking
    if booking.status != "CONFIRMED":
        raise HTTPException(status_code=400, detail=f"Only CONFIRMED bookings can be completed (current: {booking.status})")

    booking.status = "COMPLETED"
    session.add(booking)

    # 수강권 자동 차감 — 캘린더 host_id로 강사 식별
    from app.domains.passes.models import CustomerPass as CustomerPassModel
    _ts_for_pass = await session.get(TimeSlot, booking.time_slot_id)
    _cal_for_pass = await session.get(Calendar, _ts_for_pass.calendar_id) if _ts_for_pass else None
    _instructor_id_for_pass = UUID(str(_cal_for_pass.host_id)) if _cal_for_pass else None
    if _instructor_id_for_pass:
        cp_res = await session.execute(
            select(CustomerPassModel).where(
                CustomerPassModel.customer_id == UUID(str(booking.guest_id)),
                CustomerPassModel.instructor_id == _instructor_id_for_pass,
                CustomerPassModel.status == "ACTIVE",
            ).limit(1)
        )
        active_pass = cp_res.scalars().first()
        if active_pass and active_pass.sessions_used < active_pass.sessions_total:
            active_pass.sessions_used += 1
            if active_pass.sessions_used >= active_pass.sessions_total:
                active_pass.status = "COMPLETED"
            session.add(active_pass)

    # 멤버십 차감 (TIMES 타입)
    if booking.membership_id:
        mem_res = await session.execute(
            select(MembershipModel).where(MembershipModel.id == booking.membership_id)
        )
        membership = mem_res.scalar_one_or_none()
        if membership and membership.type == "TIMES" and membership.remaining_count is not None:
            membership.remaining_count = max(0, membership.remaining_count - 1)
            if membership.remaining_count == 0:
                membership.is_active = False
            session.add(membership)

    await session.commit()
    await session.refresh(booking)
    token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
    await send_push(token, "레슨 완료", f"{booking.topic} ({booking.when}) 레슨이 완료 처리되었습니다.")
    return booking


@cal_router.patch("/me/bookings/{booking_id}/no-show", response_model=BookingRead)
async def no_show_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    노쇼 처리: CONFIRMED -> NO_SHOW
    - 멤버십 차감 여부는 정책에 따라 강사가 직접 결정 (자동 차감 없음)
    """
    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can mark no-show only in your calendar")

    if booking.status == "NO_SHOW":
        return booking
    if booking.status != "CONFIRMED":
        raise HTTPException(status_code=400, detail=f"Only CONFIRMED bookings can be marked NO_SHOW (current: {booking.status})")

    booking.status = "NO_SHOW"
    session.add(booking)

    # 수강권 자동 차감 (노쇼도 차감) — 캘린더 host_id로 강사 식별
    from app.domains.passes.models import CustomerPass as CustomerPassModel
    _ts_for_pass = await session.get(TimeSlot, booking.time_slot_id)
    _cal_for_pass = await session.get(Calendar, _ts_for_pass.calendar_id) if _ts_for_pass else None
    _instructor_id_for_pass = UUID(str(_cal_for_pass.host_id)) if _cal_for_pass else None
    if _instructor_id_for_pass:
        cp_res = await session.execute(
            select(CustomerPassModel).where(
                CustomerPassModel.customer_id == UUID(str(booking.guest_id)),
                CustomerPassModel.instructor_id == _instructor_id_for_pass,
                CustomerPassModel.status == "ACTIVE",
            ).limit(1)
        )
        active_pass = cp_res.scalars().first()
        if active_pass and active_pass.sessions_used < active_pass.sessions_total:
            active_pass.sessions_used += 1
            if active_pass.sessions_used >= active_pass.sessions_total:
                active_pass.status = "COMPLETED"
            session.add(active_pass)

    await session.commit()
    await session.refresh(booking)
    return booking


@cal_router.patch("/me/bookings/{booking_id}/approve-cancel", response_model=BookingCancelResponse)
async def approve_cancel_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 고객의 취소 신청을 승인: CANCEL_REQUESTED -> CANCELLED"""
    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can only manage bookings in your calendar")

    if booking.status != "CANCEL_REQUESTED":
        raise HTTPException(status_code=400, detail=f"Invalid status: expected CANCEL_REQUESTED, got {booking.status}")

    booking.status = "CANCELLED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
    await send_push(token, "취소 승인", f"{booking.topic} ({booking.when}) 취소 신청이 승인되었습니다.")
    return BookingCancelResponse(id=booking.id, status=booking.status, updated_at=booking.updated_at)


@cal_router.patch("/me/bookings/{booking_id}/reject-cancel", response_model=BookingRead)
async def reject_cancel_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 고객의 취소 신청을 거절: CANCEL_REQUESTED -> CONFIRMED"""
    host_id = UUID(str(host.id))
    host_role = ((getattr(host, "role", None) or "").strip()).upper()

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if host_role != "ADMIN":
        ts_res = await session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))
        ts = ts_res.scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        cal_res = await session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))
        calendar = cal_res.scalar_one_or_none()
        if not calendar or UUID(str(calendar.host_id)) != host_id:
            raise HTTPException(status_code=403, detail="You can only manage bookings in your calendar")

    if booking.status != "CANCEL_REQUESTED":
        raise HTTPException(status_code=400, detail=f"Invalid status: expected CANCEL_REQUESTED, got {booking.status}")

    booking.status = "CONFIRMED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    token = await _get_guest_push_token(session, UUID(str(booking.guest_id)))
    await send_push(token, "취소 거절", f"{booking.topic} ({booking.when}) 취소 신청이 거절되었습니다. 예약이 유지됩니다.")
    return booking


@bk_router.patch("/{booking_id}/withdraw-cancel", response_model=BookingRead)
async def withdraw_cancel_as_guest(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """
    게스트(예약자) 취소 신청 철회
    - CANCEL_REQUESTED → CONFIRMED (강사가 아직 승인 전에만 가능)
    """
    user_id = UUID(str(user.id))

    res = await session.execute(select(Booking).where(Booking.id == booking_id))
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.guest_id != user_id:
        raise HTTPException(status_code=403, detail="Only the guest can withdraw this cancel request")

    if booking.status == "CONFIRMED":
        return booking

    if booking.status != "CANCEL_REQUESTED":
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CONFIRMED")

    booking.status = "CONFIRMED"
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


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