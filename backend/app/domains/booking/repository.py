# 예약 저장소: 레슨 신청·확정·취소·완료와 수강권 차감
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from icalendar import Calendar as ICal, Event as ICalEvent
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser
from app.core.clock import today_kst
from app.core.logging import log_event
from app.domains.booking.models import ACTIVE_LESSON_STATUSES, Booking, BookingSlot, BookingType
from app.domains.booking.schemas import (
    AdminBookingRead,
    BookingCleanupResponse,
    BookingCreate,
    BookingRead,
    BulkCompleteItem,
    BulkCompleteResponse,
)
from app.domains.calendar.models import Calendar, TimeSlot
from app.domains.calendar.repository import CalendarBlockRepository
from app.domains.passes.repository import PassRepository
from app.domains.users.models import User
from app.domains.users.repository import UserRepository


def _booking_conflict_detail(*, time_slot_ids: list[int], when: date, error: str) -> dict:
    return {
        "error": error,  # SLOT_ALREADY_BOOKED / BOOKING_CONFLICT
        "message": "이미 예약된 시간대입니다. 최신 일정으로 갱신 후 다시 선택해주세요."
        if error == "SLOT_ALREADY_BOOKED"
        else "예약 충돌이 발생했습니다. 최신 일정으로 갱신 후 다시 시도해주세요.",
        "hint": "REFETCH_AVAILABILITY",
        "time_slot_ids": time_slot_ids,
        "when": when.isoformat(),
    }


def _conflict(error: str, time_slot_ids: list[int], when: date) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_booking_conflict_detail(time_slot_ids=time_slot_ids, when=when, error=error),
    )


def _bad_request(detail: str) -> HTTPException:
    """요청 자체가 규칙에 맞지 않음 (다시 보내도 실패). 지금 상태와의 충돌은 _reject·_conflict(409)"""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _log(event: str, booking: Booking, actor: CurrentUser, **fields) -> None:
    """예약 사용 로그 (commit 이후에 부른다)"""
    log_event(event, booking_id=booking.id, actor_id=str(actor.id), **fields)


def _reject(detail: str) -> HTTPException:
    """현재 상태와 맞지 않는 요청 (잘못된 상태 전환, 동시 요청에서 진 쪽, 쓸 수 있는 수강권 없음)"""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# 거부 이유에 쓰는 상태 이름 (화면에 그대로 보인다)
STATUS_LABEL = {
    "REQUESTED": "신청 중", "CONFIRMED": "확정", "CANCEL_REQUESTED": "취소 신청 중",
    "CANCELLED": "취소됨", "COMPLETED": "완료", "NO_SHOW": "노쇼",
}


def _ensure_before_lesson_day(when: date, action: str) -> None:
    """수업 전날까지만 되는 동작 (신청·신청 철회·취소 신청·확정). 당일과 지난 날짜는 400

    날짜는 한국 날짜 기준이다. 시간이 지나도 될 수 없는 요청이라 409 가 아니라 400 으로 거부한다.
    """
    if when <= today_kst():
        raise _bad_request(f"{action}은 수업 전날까지만 할 수 있습니다.")


def _ensure_lesson_day_reached(when: date) -> None:
    """수업 당일부터 되는 동작 (완료·노쇼). 아직 오지 않은 수업이면 409 (그날이 되면 되는 요청)"""
    if when > today_kst():
        raise _reject("아직 수업 날짜가 되지 않은 예약입니다.")


# 자동 정리: 강사가 처리하지 않은 지난 예약을 하루 한 번 정리한다
AUTO_COMPLETE_AFTER_DAYS = 3   # 수업일 + 3일이 지나면(4일째부터) 확정 예약을 완료한다
AUTO_CANCEL_REASON = "수업 날짜가 지나 자동으로 취소되었습니다."
SYSTEM_ACTOR = "system"        # 사용 로그의 actor_id (사람이 아니라 자동 정리가 한 일)
REVERT_REASON = "관리자가 완료를 취소했습니다."
COMPLETED_LIST_DAYS = 90       # 관리자 화면의 완료 예약 목록 범위 (수업일 기준)


def _reason_values(reason: Optional[str]) -> dict:
    return {"cancel_reason": reason} if reason else {}


class BookingRepository:
    """레슨 예약 생성과 상태 전환 (휴무·영업일 전환은 CalendarBlockRepository)

    예약 1건 = 레슨 1회. 레슨이 차지하는 시간은 BookingSlot 에 슬롯마다 한 행씩 있다 (2시간 레슨이면 2행).

    날짜 규칙 (한국 날짜 기준): 신청·신청 철회·취소 신청·확정은 수업 전날까지, 완료·노쇼는 수업 당일부터.
    거절·강사 취소·취소 신청 승인/거절은 날짜 제한이 없다 (지난 예약을 정리할 수 있어야 한다).

    상태: REQUESTED → CONFIRMED → COMPLETED / NO_SHOW
                    ↘ CANCELLED (강사 거절·고객 철회)     CONFIRMED ⇄ CANCEL_REQUESTED → CANCELLED
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # 조회·권한

    async def get_or_404(self, booking_id: int) -> Booking:
        booking = (await self.session.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
        return booking

    async def host_id_of(self, booking: Booking) -> Optional[UUID]:
        cal = await self.session.get(Calendar, booking.calendar_id)
        return UUID(str(cal.host_id)) if cal else None

    async def ensure_host_can_manage(self, booking: Booking, host: CurrentUser) -> None:
        """강사는 본인 캘린더의 예약만 조작 (관리자는 전체)"""
        if (host.role or "").upper() == "ADMIN":
            return
        if await self.host_id_of(booking) != UUID(str(host.id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인 캘린더의 예약만 처리할 수 있습니다.")

    @staticmethod
    def ensure_guest(booking: Booking, user: CurrentUser) -> None:
        if booking.guest_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail="본인의 예약만 처리할 수 있습니다.")

    # 고객의 예약 목록
    async def list_by_guest(self, guest_id: UUID) -> list[Booking]:
        res = await self.session.execute(
            select(Booking).where(Booking.guest_id == guest_id).order_by(Booking.when.desc(), Booking.id.desc())
        )
        return list(res.scalars().all())

    # 강사 캘린더의 예약 목록
    async def list_by_calendar(self, calendar_id: int, start: date, end: date) -> list[Booking]:
        if end < start:
            raise HTTPException(status_code=400, detail="종료일은 시작일보다 빠를 수 없습니다.")
        res = await self.session.execute(
            select(Booking)
            .where(Booking.calendar_id == calendar_id, Booking.when >= start, Booking.when <= end)
            .order_by(Booking.when.desc(), Booking.id.desc())
        )
        return list(res.scalars().all())

    # 응답 조립

    async def read(self, booking: Booking) -> BookingRead:
        return (await self.read_many([booking]))[0]

    async def read_many(self, bookings: list[Booking]) -> list[BookingRead]:
        """예약 응답: 예약마다 차지하는 슬롯(시작 시각 순)과 시작·끝 시각을 붙인다 (슬롯 조회는 한 번)"""
        slots: dict[int, list[TimeSlot]] = {}
        if bookings:
            rows = await self.session.execute(
                select(BookingSlot.booking_id, TimeSlot)
                .join(TimeSlot, TimeSlot.id == BookingSlot.time_slot_id)
                .where(BookingSlot.booking_id.in_([b.id for b in bookings]))
                .order_by(TimeSlot.start_time, TimeSlot.id)
            )
            for booking_id, ts in rows.all():
                slots.setdefault(booking_id, []).append(ts)
        result: list[BookingRead] = []
        for b in bookings:
            mine = slots.get(b.id, [])
            result.append(BookingRead(
                id=b.id, when=b.when, topic=b.topic, status=b.status, type=b.type, description=b.description,
                cancel_reason=b.cancel_reason, guest_id=b.guest_id, customer_pass_id=b.customer_pass_id,
                created_at=b.created_at, updated_at=b.updated_at,
                time_slot_ids=[ts.id for ts in mine],
                start_time=mine[0].start_time if mine else None,
                end_time=mine[-1].end_time if mine else None,
            ))
        return result

    # 생성

    async def create(self, data: BookingCreate, user: CurrentUser) -> Booking:
        """고객(또는 관리자)의 레슨 신청 → REQUESTED. 그날 영업 중인 시간(day_status)에만 가능"""
        if data.type != BookingType.LESSON:
            raise HTTPException(status_code=400, detail="예약은 레슨만 가능합니다. 휴무·영업일 전환은 /calendars/me/blocks 를 사용하세요.")
        guest_id = UUID(str(user.id))
        user_role = ((user.role or "CUSTOMER").strip()).upper()
        if user_role not in {"CUSTOMER", "ADMIN"}:
            raise HTTPException(status_code=403, detail="예약은 고객만 신청할 수 있습니다.")
        _ensure_before_lesson_day(data.when, "예약 신청")

        slots = await self._lesson_slots(data.time_slot_ids, data.when)
        slot_ids = [ts.id for ts in slots]

        calendar = (await self.session.execute(select(Calendar).where(Calendar.id == slots[0].calendar_id))).scalar_one_or_none()
        if not calendar:
            raise HTTPException(status_code=404, detail="강사 캘린더를 찾을 수 없습니다.")

        st = await CalendarBlockRepository(self.session).day_status_for(calendar, data.when)
        if not set(slot_ids) <= st.open_slot_ids:
            detail = {"RECURRING": "강사의 정기 휴무일입니다.", "TEMPORARY": "강사의 임시 휴무일입니다."}.get(st.off_type or "", "강사가 닫은 시간입니다.")
            raise HTTPException(status_code=400, detail=detail)

        # 이 예약에 쓸 수강권을 고정한다 (지정한 것, 안 했으면 그 강사의 가장 오래된 쓸 수 있는 수강권).
        # 레슨 1회의 길이는 수강권이 정한다: 슬롯 수가 수강권의 회당 시간과 같아야 한다
        customer_pass_id = await self._pin_pass(guest_id, UUID(str(calendar.host_id)), data.customer_pass_id, len(slots))

        # 같은 날짜·슬롯을 차지하는 예약은 하나만. 고른 시간 중 하나라도 잡혀 있으면 전체를 거부한다 (반쪽 예약을 만들지 않는다)
        if await self._active_exists(slot_ids, data.when):
            raise _conflict("SLOT_ALREADY_BOOKED", slot_ids, data.when)

        booking = Booking(
            when=data.when,
            topic=data.topic,
            description=data.description,
            calendar_id=calendar.id,
            guest_id=guest_id,
            status="REQUESTED",
            type=data.type,
            customer_pass_id=customer_pass_id,
        )
        self.session.add(booking)
        try:
            await self.session.flush()  # 예약 id 를 받는다
            # 예약과 그 시간들은 한 트랜잭션: 하나라도 유니크 인덱스에 걸리면 예약도 남지 않는다.
            # 슬롯 id 순으로 넣는다 (겹치는 예약 둘이 서로 반대 순서로 넣다가 교착되지 않게)
            await self.session.execute(
                insert(BookingSlot),
                [{"booking_id": booking.id, "time_slot_id": sid, "when": data.when} for sid in sorted(slot_ids)],
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # 동시에 같은 시간을 잡은 경우
            if await self._active_exists(slot_ids, data.when):
                raise _conflict("SLOT_ALREADY_BOOKED", slot_ids, data.when)
            raise _conflict("BOOKING_CONFLICT", slot_ids, data.when)
        await self.session.refresh(booking)
        _log("booking.created", booking, user, time_slot_ids=slot_ids, when=booking.when, customer_pass_id=customer_pass_id)
        return booking

    async def _lesson_slots(self, time_slot_ids: list[int], when: date) -> list[TimeSlot]:
        """요청한 슬롯들을 시작 시각 순으로 돌려준다. 한 레슨이 될 수 없는 조합이면 거부한다

        같은 캘린더의 켜진 슬롯이고, 그 요일에 열리며, 앞 슬롯의 끝 = 다음 슬롯의 시작으로 이어져야 한다.
        """
        if len(set(time_slot_ids)) != len(time_slot_ids):
            raise _bad_request("같은 시간을 두 번 고를 수 없습니다.")
        slots = list((await self.session.execute(
            select(TimeSlot).where(TimeSlot.id.in_(time_slot_ids)).order_by(TimeSlot.start_time, TimeSlot.id)
        )).scalars().all())
        if len(slots) != len(time_slot_ids):
            raise HTTPException(status_code=404, detail="시간을 찾을 수 없습니다.")
        if len({ts.calendar_id for ts in slots}) != 1:
            raise _bad_request("한 강사의 시간만 함께 예약할 수 있습니다.")
        for ts in slots:
            if not ts.is_active:
                raise HTTPException(status_code=400, detail="강사가 사용하지 않는 시간입니다.")
            if when.weekday() not in (ts.weekdays or []):
                raise HTTPException(status_code=400, detail="선택한 날짜에는 열리지 않는 시간입니다.")
        for prev, nxt in zip(slots, slots[1:]):
            if prev.end_time != nxt.start_time:
                raise _bad_request("레슨 시간은 서로 이어져 있어야 합니다.")
        return slots

    async def _pin_pass(self, guest_id: UUID, instructor_id: UUID, requested_id: Optional[int], slot_count: int) -> int:
        """예약에 고정할 수강권 id. 남은 횟수 = 총 횟수 − 사용 − 이 수강권에 걸린 진행 중 예약 수 가 1 이상이어야 한다

        지정한 수강권이 남의 것·다른 강사의 것이면 400 (PassRepository), 쓸 수 있는 수강권이 없으면 409.
        쓸 수 있는 수강권은 있는데 회당 시간(duration_hours)이 고른 슬롯 수와 다르면 400:
        2시간 수강권으로 1시간만 예약하거나 3시간을 예약할 수 없다 (예약 1건 = 레슨 1회 = 1회 차감).
        후보 수강권 행을 잠근 상태에서 세므로, 같은 수강권으로 동시에 예약해도 남은 횟수를 넘지 않는다 (잠금은 commit 까지).
        """
        candidates = await PassRepository(self.session).lock_passes_for_booking(guest_id, instructor_id, requested_id)
        usable = []
        for cp in candidates:
            if cp.status != "ACTIVE":
                continue
            reserved = (await self.session.execute(
                select(func.count()).select_from(Booking).where(
                    Booking.customer_pass_id == cp.id, Booking.status.in_(ACTIVE_LESSON_STATUSES)
                )
            )).scalar_one()
            if cp.sessions_total - cp.sessions_used - reserved > 0:
                usable.append(cp)
        if not usable:
            raise _reject("사용할 수 있는 수강권이 없습니다.")
        for cp in usable:
            if cp.duration_hours == slot_count:
                return cp.id
        raise _bad_request(f"이 수강권은 레슨 1회가 {usable[0].duration_hours}시간입니다. 이어진 {usable[0].duration_hours}개 시간을 선택해 주세요.")

    async def _active_exists(self, time_slot_ids: list[int], when: date) -> bool:
        """그 날짜에 이 슬롯들 중 하나라도 다른 예약이 차지하고 있는가"""
        res = await self.session.execute(
            select(BookingSlot.id)
            .where(BookingSlot.time_slot_id.in_(time_slot_ids), BookingSlot.when == when, BookingSlot.holds_slot)
            .limit(1)
        )
        return res.first() is not None

    # 고객 동작

    async def update_by_guest(self, booking: Booking, user: CurrentUser, topic: Optional[str], description_set: bool, description: Optional[str]) -> Booking:
        """신청(REQUESTED) 중인 레슨의 주제·메모 수정"""
        self.ensure_guest(booking, user)
        if booking.status != "REQUESTED":
            raise HTTPException(status_code=400, detail="신청 중인 예약만 수정할 수 있습니다.")
        if topic is not None:
            booking.topic = topic
        if description_set:
            booking.description = description
        return await self._save(booking)

    async def request_cancel_by_guest(self, booking: Booking, user: CurrentUser, reason: Optional[str]) -> Booking:
        """확정된 예약의 취소 신청: CONFIRMED → CANCEL_REQUESTED (강사 승인 대기). 신청 중이면 withdraw"""
        self.ensure_guest(booking, user)
        if booking.status == "COMPLETED":
            raise _reject("완료된 예약은 취소할 수 없습니다.")
        if booking.status == "REQUESTED":
            raise _reject("신청 중인 예약은 취소 신청이 아니라 신청 철회로 처리해 주세요.")
        # 상태로 이미 안 되는 요청은 그 이유를 먼저 알려 주고, 그다음에 날짜를 본다
        _ensure_before_lesson_day(booking.when, "취소 신청")
        await self._transition(booking, "CONFIRMED", "CANCEL_REQUESTED", **_reason_values(reason))
        booking = await self._save(booking)
        _log("booking.cancel_requested", booking, user)
        guest = await self.session.get(User, UUID(str(booking.guest_id)))
        guest_name = guest.display_name if guest else "고객"
        await UserRepository(self.session).notify(
            await self.host_id_of(booking), "취소 신청",
            f"{guest_name}님이 {booking.topic} ({booking.when}) 취소를 신청했습니다.",
            {"booking_id": booking.id},
        )
        return booking

    async def withdraw_by_guest(self, booking: Booking, user: CurrentUser, reason: Optional[str]) -> Booking:
        """신청 철회: REQUESTED → CANCELLED"""
        self.ensure_guest(booking, user)
        if booking.status == "COMPLETED":
            raise _reject("완료된 예약은 철회할 수 없습니다.")
        _ensure_before_lesson_day(booking.when, "신청 철회")
        await self._transition(booking, "REQUESTED", "CANCELLED", **_reason_values(reason))
        booking = await self._save(booking)
        _log("booking.withdrawn", booking, user)
        return booking

    async def withdraw_cancel_by_guest(self, booking: Booking, user: CurrentUser) -> Booking:
        """취소 신청 철회: CANCEL_REQUESTED → CONFIRMED (강사 승인 전)"""
        self.ensure_guest(booking, user)
        await self._transition(booking, "CANCEL_REQUESTED", "CONFIRMED")
        booking = await self._save(booking)
        _log("booking.cancel_withdrawn", booking, user)
        return booking

    # 강사 동작

    async def confirm(self, booking: Booking, host: CurrentUser, topic: Optional[str]) -> Booking:
        """확정: REQUESTED → CONFIRMED (강사가 수업 내용 지정 가능)"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status == "CANCELLED":
            raise _reject("취소된 예약은 확정할 수 없습니다.")
        _ensure_before_lesson_day(booking.when, "예약 확정")
        await self._transition(booking, "REQUESTED", "CONFIRMED", **({"topic": topic} if topic else {}))
        booking = await self._save(booking)
        _log("booking.confirmed", booking, host)
        await self._push_guest(booking, "예약 확정", f"{booking.topic} ({booking.when}) 예약이 확정되었습니다.")
        return booking

    async def decline(self, booking: Booking, host: CurrentUser, reason: Optional[str]) -> Booking:
        """거절: REQUESTED → CANCELLED (슬롯 다시 열림). 확정 이후는 cancel"""
        await self.ensure_host_can_manage(booking, host)
        await self._transition(booking, "REQUESTED", "CANCELLED", **_reason_values(reason))
        booking = await self._save(booking)
        _log("booking.declined", booking, host)
        await self._push_guest(booking, "예약 신청 거절", f"{booking.topic} ({booking.when}) 예약 신청이 거절되었습니다.")
        return booking

    async def cancel_by_host(self, booking: Booking, host: CurrentUser, reason: Optional[str]) -> Booking:
        """강사 취소: CONFIRMED → CANCELLED (신청 중은 decline)"""
        await self.ensure_host_can_manage(booking, host)
        if booking.status == "COMPLETED":
            raise _reject("완료된 예약은 취소할 수 없습니다.")
        if booking.status == "REQUESTED":
            raise _reject("신청 중인 예약은 취소가 아니라 거절로 처리해 주세요.")
        await self._transition(booking, "CONFIRMED", "CANCELLED", **_reason_values(reason))
        booking = await self._save(booking)
        _log("booking.cancelled", booking, host)
        await self._push_guest(booking, "예약 취소", f"{booking.topic} ({booking.when}) 예약이 취소되었습니다.")
        return booking

    async def complete(self, booking: Booking, host: CurrentUser) -> Booking:
        """출석 완료: CONFIRMED → COMPLETED. 수강권 1회 차감 (쓸 수 있는 수강권이 없으면 409, 예약도 그대로)"""
        customer_pass_id = await self.complete_uncommitted(booking, host)
        booking = await self._save(booking)
        await self.announce_completed(booking, host, customer_pass_id)
        return booking

    async def complete_uncommitted(self, booking: Booking, host: CurrentUser) -> int:
        """완료의 DB 변경만 한다 (상태 전환 + 수강권 1회 차감). commit 하지 않고, 차감한 수강권 id 를 돌려준다

        완료와 함께 저장할 것이 있는 쪽(레슨노트)이 같은 트랜잭션에 넣고 한 번에 commit 하려고 쓴다.
        commit 한 뒤에는 announce_completed 를 부른다.
        """
        await self.ensure_host_can_manage(booking, host)
        return await self._use_lesson(booking, str(host.id), "COMPLETED", "booking.complete_rejected")

    async def announce_completed(self, booking: Booking, host: CurrentUser, customer_pass_id: int) -> None:
        """완료가 commit 된 뒤: 사용 로그와 고객 푸시"""
        _log("booking.completed", booking, host, customer_pass_id=customer_pass_id)
        await self._push_guest(booking, "레슨 완료", f"{booking.topic} ({booking.when}) 레슨이 완료 처리되었습니다.")

    async def complete_many(self, booking_ids: list[int], host: CurrentUser) -> BulkCompleteResponse:
        """여러 예약을 한 번에 완료한다. 결과는 레슨 날짜가 빠른 순으로 하나씩 완료했을 때와 같다

        - 요청 자체가 잘못됐으면(없는 번호, 다른 강사의 예약) 아무것도 처리하지 않고 404.
          없는 번호와 남의 번호를 같은 응답으로 묶어, 남의 예약 번호가 있는지 드러나지 않게 한다
        - 그 밖에는 건별 결과: 그사이 상태가 바뀌었거나 수강권이 모자란 건(409)만 실패로 남고 나머지는 완료된다.
          예약마다 따로 commit 하므로 한 건의 실패가 다른 건을 되돌리지 않는다
        같은 번호가 두 번 들어 있으면 한 번만 처리한다.
        """
        wanted = list(dict.fromkeys(booking_ids))
        rows = (await self.session.execute(
            select(Booking.id, Booking.when, Booking.calendar_id).where(Booking.id.in_(wanted))
        )).all()
        allowed = len(rows) == len(wanted)
        if allowed and (host.role or "").upper() != "ADMIN":
            my_calendar = (await self.session.execute(
                select(Calendar.id).where(Calendar.host_id == UUID(str(host.id)))
            )).scalar_one_or_none()
            allowed = all(calendar_id == my_calendar for _, _, calendar_id in rows)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="예약을 찾을 수 없습니다.")

        results: list[BulkCompleteItem] = []
        for booking_id, _, _ in sorted(rows, key=lambda row: (row[1], row[0])):
            try:
                booking = await self.complete(await self.get_or_404(booking_id), host)
                results.append(BulkCompleteItem(booking_id=booking_id, ok=True, status=booking.status))
            except HTTPException as e:
                if e.status_code != status.HTTP_409_CONFLICT:
                    raise
                # 이 건만 실패: 이 건의 변경을 되돌리고 다음 건으로 넘어간다 (앞에서 완료한 건은 이미 commit 됨)
                await self.session.rollback()
                current = (await self.session.execute(select(Booking.status).where(Booking.id == booking_id))).scalar_one_or_none()
                results.append(BulkCompleteItem(booking_id=booking_id, ok=False, status=current, message=str(e.detail)))
        completed = sum(1 for r in results if r.ok)
        log_event("booking.bulk_completed", actor_id=str(host.id), requested=len(wanted), completed=completed,
                  failed=len(results) - completed)
        return BulkCompleteResponse(results=results, completed=completed, failed=len(results) - completed)

    async def mark_no_show(self, booking: Booking, host: CurrentUser) -> Booking:
        """노쇼: CONFIRMED → NO_SHOW. 수강권은 차감 (쓸 수 있는 수강권이 없으면 409, 예약도 그대로)"""
        await self.ensure_host_can_manage(booking, host)
        customer_pass_id = await self._use_lesson(booking, str(host.id), "NO_SHOW", "booking.no_show_rejected")
        booking = await self._save(booking)
        _log("booking.no_show", booking, host, customer_pass_id=customer_pass_id)
        return booking

    async def approve_cancel(self, booking: Booking, host: CurrentUser) -> Booking:
        """취소 신청 승인: CANCEL_REQUESTED → CANCELLED"""
        await self.ensure_host_can_manage(booking, host)
        await self._transition(booking, "CANCEL_REQUESTED", "CANCELLED")
        booking = await self._save(booking)
        _log("booking.cancel_request_approved", booking, host)
        await self._push_guest(booking, "취소 승인", f"{booking.topic} ({booking.when}) 취소 신청이 승인되었습니다.")
        return booking

    async def reject_cancel(self, booking: Booking, host: CurrentUser) -> Booking:
        """취소 신청 거절: CANCEL_REQUESTED → CONFIRMED"""
        await self.ensure_host_can_manage(booking, host)
        await self._transition(booking, "CANCEL_REQUESTED", "CONFIRMED")
        booking = await self._save(booking)
        _log("booking.cancel_request_declined", booking, host)
        await self._push_guest(booking, "취소 거절", f"{booking.topic} ({booking.when}) 취소 신청이 거절되었습니다. 예약이 유지됩니다.")
        return booking

    # 캘린더 파일 (.ics)

    async def ics_for(self, booking: Booking, user: CurrentUser) -> bytes:
        """예약한 고객, 그 캘린더의 강사, 관리자만 받을 수 있다"""
        if (user.role or "").upper() != "ADMIN":
            uid = UUID(str(user.id))
            if booking.guest_id != uid and await self.host_id_of(booking) != uid:
                raise HTTPException(status_code=403, detail="권한이 없습니다.")

        read = await self.read(booking)
        if read.start_time is None or read.end_time is None:
            raise HTTPException(status_code=404, detail="시간을 찾을 수 없습니다.")

        cal = ICal()
        event = ICalEvent()
        event.add("summary", f"[CRM 예약] {booking.topic}")
        event.add("description", booking.description or "CRM 앱에서 생성된 예약입니다.")
        event.add("dtstart", datetime.combine(booking.when, read.start_time))
        event.add("dtend", datetime.combine(booking.when, read.end_time))
        event.add("dtstamp", datetime.now())
        cal.add_component(event)
        return cal.to_ical()

    async def list_completed_for_admin(self) -> list[AdminBookingRead]:
        """관리자 화면: 최근 90일 안에 수업한 완료 예약 (최근 수업부터), 강사·고객 이름 포함"""
        since = today_kst() - timedelta(days=COMPLETED_LIST_DAYS)
        bookings = list((await self.session.execute(
            select(Booking)
            .where(Booking.type == BookingType.LESSON, Booking.status == "COMPLETED", Booking.when >= since)
            .order_by(Booking.when.desc(), Booking.id.desc())
        )).scalars().all())
        hosts = dict((await self.session.execute(
            select(Calendar.id, Calendar.host_id).where(Calendar.id.in_({b.calendar_id for b in bookings}))
        )).all()) if bookings else {}
        people = {*hosts.values(), *(b.guest_id for b in bookings)}
        names = dict((await self.session.execute(
            select(User.id, User.display_name).where(User.id.in_(people))
        )).all()) if people else {}
        return [
            AdminBookingRead(
                **read.model_dump(),
                instructor_id=hosts.get(b.calendar_id),
                instructor_name=names.get(hosts.get(b.calendar_id)),
                guest_name=names.get(b.guest_id),
            )
            for b, read in zip(bookings, await self.read_many(bookings))
        ]

    async def revert_complete(self, booking: Booking, admin: CurrentUser, reason: Optional[str]) -> Booking:
        """관리자의 완료 되돌리기: COMPLETED → CANCELLED + 고정된 수강권에 1회 복구 (시간도 다시 비운다)

        확정으로 되돌리지 않는다: 수업일이 지난 확정 예약은 자동 정리가 다시 완료·차감한다.
        수업을 다시 잡으려면 새로 예약한다. 누가 부를 수 있는지는 router 가 정한다 (관리자만).
        수강권이 고정되지 않은 예전 예약은 어느 수강권에서 차감됐는지 알 수 없어 거부한다 (409).
        """
        if booking.status == "COMPLETED" and booking.customer_pass_id is None:
            raise _reject("수강권 기록이 없는 예전 예약은 되돌릴 수 없습니다. 수강권 횟수를 직접 고쳐 주세요.")
        detail = f"{REVERT_REASON} ({reason.strip()})" if reason and reason.strip() else REVERT_REASON
        await self._transition(booking, "COMPLETED", "CANCELLED", cancel_reason=detail)
        customer_pass_id = await PassRepository(self.session).restore_for_lesson(booking.customer_pass_id)
        booking = await self._save(booking)
        _log("booking.complete_reverted", booking, admin, customer_pass_id=customer_pass_id)
        body = f"{booking.topic} ({booking.when}) 레슨의 완료 처리가 취소되고 수강권 1회가 복구되었습니다."
        await self._push_guest(booking, "레슨 완료 취소", body)
        await UserRepository(self.session).notify(await self.host_id_of(booking), "레슨 완료 취소", body, {"booking_id": booking.id})
        return booking

    async def cleanup_past(self) -> BookingCleanupResponse:
        """지난 예약 자동 정리 (하루 한 번, 예약 실행이 부른다). 여러 번 불러도 결과는 같다

        - 수업일 + 3일이 지난 확정 예약 → 완료 + 수강권 1회 차감 (강사·고객에게 알림).
          차감할 수 없는 건(수강권을 다 씀)은 확정으로 남기고 거부 로그를 남긴다
        - 수업 날짜가 지난 신청 → 취소 (고객에게 알림). 신청을 대신 확정하지는 않는다
        - 수업일이 지난 '취소 신청 중'은 건드리지 않는다 (차감할지는 강사가 정한다). 건수만 센다
        예약마다 따로 commit 하므로 한 건의 실패가 다른 건을 되돌리지 않는다.
        강사가 같은 순간에 처리한 건은 조건부 UPDATE 에서 409 가 되어 건너뛴다.
        """
        today = today_kst()
        lesson = Booking.type == BookingType.LESSON

        async def ids_of(*conditions) -> list[int]:
            rows = await self.session.execute(select(Booking.id).where(lesson, *conditions).order_by(Booking.when, Booking.id))
            return list(rows.scalars().all())

        completed = left_confirmed = 0
        complete_before = today - timedelta(days=AUTO_COMPLETE_AFTER_DAYS)
        for booking_id in await ids_of(Booking.status == "CONFIRMED", Booking.when < complete_before):
            try:
                booking = await self.get_or_404(booking_id)
                customer_pass_id = await self._use_lesson(booking, SYSTEM_ACTOR, "COMPLETED", "booking.auto_complete_rejected")
                booking = await self._save(booking)
            except HTTPException as e:
                if e.status_code != status.HTTP_409_CONFLICT:
                    raise
                await self.session.rollback()
                # 그사이 강사가 처리했으면 남은 것이 아니다. 아직 확정이면 차감하지 못해 남긴 것이다
                still = (await self.session.execute(select(Booking.status).where(Booking.id == booking_id))).scalar_one_or_none()
                left_confirmed += still == "CONFIRMED"
                continue
            completed += 1
            log_event("booking.auto_completed", booking_id=booking.id, actor_id=SYSTEM_ACTOR, customer_pass_id=customer_pass_id)
            body = f"{booking.topic} ({booking.when}) 레슨이 수업 후 {AUTO_COMPLETE_AFTER_DAYS}일이 지나 자동으로 완료 처리되었습니다."
            await self._push_guest(booking, "레슨 자동 완료", body)
            await UserRepository(self.session).notify(await self.host_id_of(booking), "레슨 자동 완료", body, {"booking_id": booking.id})

        cancelled = 0
        for booking_id in await ids_of(Booking.status == "REQUESTED", Booking.when < today):
            try:
                booking = await self.get_or_404(booking_id)
                await self._transition(booking, "REQUESTED", "CANCELLED", cancel_reason=AUTO_CANCEL_REASON)
                booking = await self._save(booking)
            except HTTPException as e:
                if e.status_code != status.HTTP_409_CONFLICT:
                    raise
                await self.session.rollback()
                continue
            cancelled += 1
            log_event("booking.auto_cancelled", booking_id=booking.id, actor_id=SYSTEM_ACTOR)
            await self._push_guest(booking, "예약 신청 취소", f"{booking.topic} ({booking.when}) 신청이 수업 날짜가 지나 자동으로 취소되었습니다.")

        pending = (await self.session.execute(
            select(func.count()).select_from(Booking).where(lesson, Booking.status == "CANCEL_REQUESTED", Booking.when < today)
        )).scalar_one()
        result = BookingCleanupResponse(
            completed=completed, cancelled=cancelled, left_confirmed=left_confirmed, pending_cancel_requests=pending
        )
        log_event("booking.cleanup", actor_id=SYSTEM_ACTOR, **result.model_dump())
        return result

    # 내부

    async def _transition(self, booking: Booking, expected: str, new_status: str, **values) -> None:
        """상태 전환: 예약이 아직 expected 상태일 때만 new_status 로 바꾼다 (조건부 UPDATE, commit 은 호출한 쪽에서)

        읽은 상태를 Python 에서 확인하고 저장하면, 동시에 온 요청이 모두 같은 상태를 읽고 통과해
        나중에 저장한 쪽이 앞 결과를 덮어쓴다. WHERE status = expected 로 바꾸면 하나만 성공한다.
        나중 요청의 UPDATE 는 앞 트랜잭션의 커밋을 기다린 뒤 WHERE 를 다시 확인하므로 바뀐 행이 0 → 409.
        """
        if booking.status != expected:
            raise _reject(f"지금 상태({STATUS_LABEL.get(booking.status, booking.status)})에서는 할 수 없는 처리입니다.")
        res = await self.session.execute(
            update(Booking)
            .where(Booking.id == booking.id, Booking.status == expected)
            .values(status=new_status, **values)
            .returning(Booking.id)
            .execution_options(synchronize_session=False)
        )
        if res.first() is None:
            raise _reject("다른 요청이 먼저 처리되어 예약 상태가 바뀌었습니다. 새로 고친 뒤 다시 확인해 주세요.")
        if new_status == "CANCELLED":
            # 취소된 예약은 시간을 더 차지하지 않는다 (같은 트랜잭션: 상태와 시간이 어긋난 채 남지 않는다)
            await self.session.execute(
                update(BookingSlot).where(BookingSlot.booking_id == booking.id).values(holds_slot=False)
            )
        await self.session.refresh(booking)  # 이 트랜잭션 안에서 바뀐 값으로 맞춘다

    async def _save(self, booking: Booking) -> Booking:
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def _use_lesson(self, booking: Booking, actor_id: str, new_status: str, rejected_event: str) -> int:
        """완료·노쇼 공통: CONFIRMED → new_status + 수강권 1회 차감, 차감한 수강권 id 를 돌려준다 (commit 은 호출한 쪽에서)

        409 로 거부되면(상태가 맞지 않음, 쓸 수 있는 수강권 없음) 거부 사용 로그를 남기고 다시 던진다.
        실제로 완료된 건과 섞이지 않게 이벤트 이름을 따로 쓴다.
        """
        booking_id = booking.id
        try:
            _ensure_lesson_day_reached(booking.when)
            await self._transition(booking, "CONFIRMED", new_status)
            return await self._deduct_pass(booking)
        except HTTPException as e:
            if e.status_code == status.HTTP_409_CONFLICT:
                log_event(rejected_event, booking_id=booking_id, actor_id=actor_id, reason=str(e.detail))
            raise

    # 완료·노쇼 시 예약에 고정된 수강권에서 1회 차감
    async def _deduct_pass(self, booking: Booking) -> int:
        instructor_id = await self.host_id_of(booking)
        if not instructor_id or booking.customer_pass_id is None:
            raise _reject("사용할 수 있는 수강권이 없습니다.")
        return await PassRepository(self.session).deduct_for_lesson(
            booking.customer_pass_id, UUID(str(booking.guest_id)), instructor_id
        )

    # 고객에게 푸시 알림 (알림을 누르면 앱이 booking_id 로 예약 상세를 연다)
    async def _push_guest(self, booking: Booking, title: str, body: str) -> None:
        await UserRepository(self.session).notify(
            UUID(str(booking.guest_id)), title, body, {"booking_id": booking.id}
        )
