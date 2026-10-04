from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from icalendar import Calendar as ICal, Event as ICalEvent
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser
from app.core.push import send_push
from app.domains.booking.models import Booking, BookingType
from app.domains.booking.schemas import BookingCreate
from app.domains.calendar.models import Calendar, TimeSlot
from app.domains.calendar.repository import CalendarBlockRepository
from app.domains.passes.repository import PassRepository
from app.domains.users.models import User


def _booking_conflict_detail(*, time_slot_id: int, when: date, error: str) -> dict:
    return {
        "error": error,  # SLOT_ALREADY_BOOKED / BOOKING_CONFLICT
        "message": "이미 예약된 시간대입니다. 최신 일정으로 갱신 후 다시 선택해주세요."
        if error == "SLOT_ALREADY_BOOKED"
        else "예약 충돌이 발생했습니다. 최신 일정으로 갱신 후 다시 시도해주세요.",
        "hint": "REFETCH_AVAILABILITY",
        "time_slot_id": time_slot_id,
        "when": when.isoformat(),
    }


def _conflict(error: str, time_slot_id: int, when: date) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_booking_conflict_detail(time_slot_id=time_slot_id, when=when, error=error),
    )


class BookingRepository:
    """레슨 예약 생성과 상태 전환 (휴무·영업일 전환은 CalendarBlockRepository)

    상태: REQUESTED → CONFIRMED → COMPLETED / NO_SHOW
                    ↘ CANCELLED (강사 거절·고객 철회)     CONFIRMED ⇄ CANCEL_REQUESTED → CANCELLED
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 조회·권한 ────────────────────────────────────────────────────────────

    async def get_or_404(self, booking_id: int) -> Booking:
        booking = (await self.session.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return booking

    async def host_id_of(self, booking: Booking) -> Optional[UUID]:
        ts = await self.session.get(TimeSlot, booking.time_slot_id)
        cal = await self.session.get(Calendar, ts.calendar_id) if ts else None
        return UUID(str(cal.host_id)) if cal else None

    async def ensure_host_can_manage(self, booking: Booking, host: CurrentUser) -> None:
        """강사는 본인 캘린더의 예약만 조작 (관리자는 전체)"""
        if (host.role or "").upper() == "ADMIN":
            return
        ts = await self.session.get(TimeSlot, booking.time_slot_id)
        if not ts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TimeSlot not found")
        cal = await self.session.get(Calendar, ts.calendar_id)
        if not cal or UUID(str(cal.host_id)) != UUID(str(host.id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage bookings in your calendar")

    @staticmethod
    def ensure_guest(booking: Booking, user: CurrentUser, action: str) -> None:
        if booking.guest_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail=f"Only the guest can {action}")

    async def list_by_guest(self, guest_id: UUID) -> list[Booking]:
        res = await self.session.execute(
            select(Booking).where(Booking.guest_id == guest_id).order_by(Booking.when.desc(), Booking.id.desc())
        )
        return list(res.scalars().all())

    async def list_by_calendar(self, calendar_id: int, start: date, end: date) -> list[Booking]:
        if end < start:
            raise HTTPException(status_code=400, detail="end must be >= start")
        res = await self.session.execute(
            select(Booking)
            .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
            .where(TimeSlot.calendar_id == calendar_id, Booking.when >= start, Booking.when <= end)
            .order_by(Booking.when.desc(), Booking.id.desc())
        )
        return list(res.scalars().all())

    # ── 생성 ─────────────────────────────────────────────────────────────────

    async def create(self, data: BookingCreate, user: CurrentUser) -> Booking:
        """고객(또는 관리자)의 레슨 신청 → REQUESTED. 그날 영업 중인 시간(day_status)에만 가능"""
        if data.type != BookingType.LESSON:
            raise HTTPException(status_code=400, detail="예약은 레슨만 가능합니다. 휴무·영업일 전환은 /calendars/me/blocks 를 사용하세요.")
        guest_id = UUID(str(user.id))
        user_role = ((user.role or "CUSTOMER").strip()).upper()
        if user_role not in {"CUSTOMER", "ADMIN"}:
            raise HTTPException(status_code=403, detail="Only customer can request a LESSON booking")

        ts = (await self.session.execute(select(TimeSlot).where(TimeSlot.id == data.time_slot_id))).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        if not ts.is_active:
            raise HTTPException(status_code=400, detail="TimeSlot is inactive")
        if data.when.weekday() not in (ts.weekdays or []):
            raise HTTPException(status_code=400, detail="Selected date is not available for this time slot")

        calendar = (await self.session.execute(select(Calendar).where(Calendar.id == ts.calendar_id))).scalar_one_or_none()
        if not calendar:
            raise HTTPException(status_code=404, detail="Calendar not found")

        st = await CalendarBlockRepository(self.session).day_status_for(calendar, data.when)
        if ts.id not in st.open_slot_ids:
            detail = {"RECURRING": "강사의 정기 휴무일입니다.", "TEMPORARY": "강사의 임시 휴무일입니다."}.get(st.off_type or "", "강사가 닫은 시간입니다.")
            raise HTTPException(status_code=400, detail=detail)
        initial_status = "REQUESTED"

        # 같은 날짜·슬롯의 (취소 아닌) 예약은 하나만
        if await self._active_exists(data.time_slot_id, data.when, data.type):
            raise _conflict("SLOT_ALREADY_BOOKED", data.time_slot_id, data.when)

        booking = Booking(
            when=data.when,
            topic=data.topic,
            description=data.description,
            time_slot_id=data.time_slot_id,
            guest_id=guest_id,
            status=initial_status,
            type=data.type,
        )
        self.session.add(booking)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # 동시에 같은 시간을 잡은 경우
            if await self._active_exists(data.time_slot_id, data.when, data.type):
                raise _conflict("SLOT_ALREADY_BOOKED", data.time_slot_id, data.when)
            raise _conflict("BOOKING_CONFLICT", data.time_slot_id, data.when)
        await self.session.refresh(booking)
        return booking

    async def _active_exists(self, time_slot_id: int, when: date, booking_type: BookingType) -> bool:
        res = await self.session.execute(
            select(Booking.id).where(
                Booking.time_slot_id == time_slot_id,
                Booking.when == when,
                Booking.status != "CANCELLED",
                Booking.type == booking_type,
            )
        )
        return res.scalar_one_or_none() is not None

    # ── 고객 동작 ────────────────────────────────────────────────────────────

    async def update_by_guest(self, booking: Booking, user: CurrentUser, topic: Optional[str], description_set: bool, description: Optional[str]) -> Booking:
        """신청(REQUESTED) 중인 레슨의 주제·메모 수정"""
        self.ensure_guest(booking, user, "modify this booking")
        if booking.status != "REQUESTED":
            raise HTTPException(status_code=400, detail="Only REQUESTED bookings can be modified")
        if topic is not None:
            booking.topic = topic
        if description_set:
            booking.description = description
        return await self._save(booking)

    async def request_cancel_by_guest(self, booking: Booking, user: CurrentUser, reason: Optional[str]) -> Booking:
        """확정된 예약의 취소 신청: CONFIRMED → CANCEL_REQUESTED (강사 승인 대기). 신청 중이면 withdraw"""
        self.ensure_guest(booking, user, "cancel this booking")
        if booking.status in ("CANCELLED", "CANCEL_REQUESTED"):
            return booking
        if booking.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="Completed booking cannot be cancelled")
        if booking.status == "REQUESTED":
            raise HTTPException(status_code=400, detail="Requested booking should be withdrawn, not cancelled")
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCEL_REQUESTED")
        booking.status = "CANCEL_REQUESTED"
        if reason:
            booking.cancel_reason = reason
        booking = await self._save(booking)
        guest = await self.session.get(User, UUID(str(booking.guest_id)))
        guest_name = guest.display_name if guest else "고객"
        await send_push(await self._host_push_token(booking), "취소 신청", f"{guest_name}님이 {booking.topic} ({booking.when}) 취소를 신청했습니다.")
        return booking

    async def withdraw_by_guest(self, booking: Booking, user: CurrentUser, reason: Optional[str]) -> Booking:
        """신청 철회: REQUESTED → CANCELLED"""
        self.ensure_guest(booking, user, "withdraw this booking")
        if booking.status == "CANCELLED":
            return booking
        if booking.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="Completed booking cannot be withdrawn")
        if booking.status != "REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")
        booking.status = "CANCELLED"
        if reason:
            booking.cancel_reason = reason
        return await self._save(booking)

    async def withdraw_cancel_by_guest(self, booking: Booking, user: CurrentUser) -> Booking:
        """취소 신청 철회: CANCEL_REQUESTED → CONFIRMED (강사 승인 전)"""
        self.ensure_guest(booking, user, "withdraw this cancel request")
        if booking.status == "CONFIRMED":
            return booking
        if booking.status != "CANCEL_REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CONFIRMED")
        booking.status = "CONFIRMED"
        return await self._save(booking)

    # ── 강사 동작 ────────────────────────────────────────────────────────────

    async def confirm(self, booking: Booking, host: CurrentUser, topic: Optional[str]) -> Booking:
        """확정: REQUESTED → CONFIRMED (강사가 수업 내용 지정 가능)"""
        if booking.status == "CONFIRMED":
            return booking
        if booking.status == "CANCELLED":
            raise HTTPException(status_code=400, detail="Cancelled booking cannot be confirmed")
        if booking.status != "REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CONFIRMED")
        await self.ensure_host_can_manage(booking, host)
        booking.status = "CONFIRMED"
        if topic:
            booking.topic = topic
        booking = await self._save(booking)
        await self._push_guest(booking, "예약 확정", f"{booking.topic} ({booking.when}) 예약이 확정되었습니다.")
        return booking

    async def decline(self, booking: Booking, host: CurrentUser, reason: Optional[str]) -> Booking:
        """거절: REQUESTED → CANCELLED (슬롯 다시 열림). 확정 이후는 cancel"""
        if booking.status == "CANCELLED":
            return booking
        if booking.status != "REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")
        await self.ensure_host_can_manage(booking, host)
        booking.status = "CANCELLED"
        if reason:
            booking.cancel_reason = reason
        booking = await self._save(booking)
        await self._push_guest(booking, "예약 신청 거절", f"{booking.topic} ({booking.when}) 예약 신청이 거절되었습니다.")
        return booking

    async def cancel_by_host(self, booking: Booking, host: CurrentUser, reason: Optional[str]) -> Booking:
        """강사 취소: CONFIRMED → CANCELLED (신청 중은 decline)"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status == "CANCELLED":
            return booking
        if booking.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="Completed booking cannot be cancelled")
        if booking.status == "REQUESTED":
            raise HTTPException(status_code=400, detail="Requested booking should be declined, not cancelled")
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {booking.status} -> CANCELLED")
        booking.status = "CANCELLED"
        if reason:
            booking.cancel_reason = reason
        booking = await self._save(booking)
        await self._push_guest(booking, "예약 취소", f"{booking.topic} ({booking.when}) 예약이 취소되었습니다.")
        return booking

    async def complete(self, booking: Booking, host: CurrentUser) -> Booking:
        """출석 완료: CONFIRMED → COMPLETED. 수강권 1회 차감"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status == "COMPLETED":
            return booking
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Only CONFIRMED bookings can be completed (current: {booking.status})")
        booking.status = "COMPLETED"
        self.session.add(booking)
        await self._deduct_pass(booking)
        booking = await self._save(booking)
        await self._push_guest(booking, "레슨 완료", f"{booking.topic} ({booking.when}) 레슨이 완료 처리되었습니다.")
        return booking

    async def mark_no_show(self, booking: Booking, host: CurrentUser) -> Booking:
        """노쇼: CONFIRMED → NO_SHOW. 수강권은 차감"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status == "NO_SHOW":
            return booking
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail=f"Only CONFIRMED bookings can be marked NO_SHOW (current: {booking.status})")
        booking.status = "NO_SHOW"
        self.session.add(booking)
        await self._deduct_pass(booking)
        return await self._save(booking)

    async def approve_cancel(self, booking: Booking, host: CurrentUser) -> Booking:
        """취소 신청 승인: CANCEL_REQUESTED → CANCELLED"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status != "CANCEL_REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status: expected CANCEL_REQUESTED, got {booking.status}")
        booking.status = "CANCELLED"
        booking = await self._save(booking)
        await self._push_guest(booking, "취소 승인", f"{booking.topic} ({booking.when}) 취소 신청이 승인되었습니다.")
        return booking

    async def reject_cancel(self, booking: Booking, host: CurrentUser) -> Booking:
        """취소 신청 거절: CANCEL_REQUESTED → CONFIRMED"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status != "CANCEL_REQUESTED":
            raise HTTPException(status_code=400, detail=f"Invalid status: expected CANCEL_REQUESTED, got {booking.status}")
        booking.status = "CONFIRMED"
        booking = await self._save(booking)
        await self._push_guest(booking, "취소 거절", f"{booking.topic} ({booking.when}) 취소 신청이 거절되었습니다. 예약이 유지됩니다.")
        return booking

    # ── 캘린더 파일 (.ics) ───────────────────────────────────────────────────

    async def ics_for(self, booking: Booking, user: CurrentUser) -> bytes:
        """예약한 고객, 그 캘린더의 강사, 관리자만 받을 수 있다"""
        if (user.role or "").upper() != "ADMIN":
            uid = UUID(str(user.id))
            if booking.guest_id != uid and await self.host_id_of(booking) != uid:
                raise HTTPException(status_code=403, detail="Forbidden")

        ts = (await self.session.execute(select(TimeSlot).where(TimeSlot.id == booking.time_slot_id))).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")

        cal = ICal()
        event = ICalEvent()
        event.add("summary", f"[CRM 예약] {booking.topic}")
        event.add("description", booking.description or "CRM 앱에서 생성된 예약입니다.")
        event.add("dtstart", datetime.combine(booking.when, ts.start_time))
        event.add("dtend", datetime.combine(booking.when, ts.end_time))
        event.add("dtstamp", datetime.now())
        cal.add_component(event)
        return cal.to_ical()

    # ── 내부 ─────────────────────────────────────────────────────────────────

    async def _save(self, booking: Booking) -> Booking:
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def _deduct_pass(self, booking: Booking) -> None:
        instructor_id = await self.host_id_of(booking)
        if instructor_id:
            await PassRepository(self.session).deduct_for_lesson(UUID(str(booking.guest_id)), instructor_id)

    async def _push_guest(self, booking: Booking, title: str, body: str) -> None:
        guest = await self.session.get(User, UUID(str(booking.guest_id)))
        await send_push(getattr(guest, "push_token", None) if guest else None, title, body)

    async def _host_push_token(self, booking: Booking) -> Optional[str]:
        host_id = await self.host_id_of(booking)
        host = await self.session.get(User, host_id) if host_id else None
        return getattr(host, "push_token", None) if host else None
