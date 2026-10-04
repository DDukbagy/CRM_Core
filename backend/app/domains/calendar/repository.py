from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.models import ACTIVE_LESSON_STATUSES, Booking, BookingType
from app.domains.calendar.models import BlockKind, Calendar, CalendarBlock, TimeSlot
from app.domains.calendar.schemas import (
    AvailabilityDay,
    AvailabilityResponse,
    AvailabilitySlot,
    CalendarCreate,
    CalendarUpdate,
    TimeSlotCreate,
    TimeSlotUpdate,
)
from app.domains.users.models import User

# 모든 강사 캘린더의 기본 슬롯: 매일 07:00~20:00, 1시간 단위 13개 (사용자 결정 2026-10-01)
DEFAULT_SLOT_HOURS = range(7, 20)
ALL_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]



@dataclass
class DayStatus:
    """한 날짜의 영업 상태. off_type: RECURRING(정기 휴무일) / TEMPORARY(임시 휴무일) / None(영업)"""
    off_type: Optional[str]
    open_slot_ids: set[int]


def day_status(day: date, slots: list[TimeSlot], recurring_off_days: set[int], blocks: list[CalendarBlock]) -> DayStatus:
    """휴무 규칙 (가용 시간 조회와 예약 생성이 같은 규칙을 쓴다)

    1. 그날 하루 전체를 닫았으면(CLOSE, 시간 없음) → 임시 휴무일
    2. 정기 휴무 요일이면 → 그날을 연(OPEN) 시간만 영업. 연 것이 없으면 정기 휴무일
    3. 그 밖의 날은 그 요일의 켜진 슬롯 전부 영업
    → 영업 시간에서 그날 닫은 시간(CLOSE, 시간 지정)은 뺀다
    """
    wd = day.weekday()
    base = {s.id for s in slots if s.is_active and wd in (s.weekdays or [])}
    todays = [b for b in blocks if b.start_date <= day <= b.end_date]
    closed = {b.time_slot_id for b in todays if b.kind == BlockKind.CLOSE.value and b.time_slot_id is not None}

    if any(b.kind == BlockKind.CLOSE.value and b.time_slot_id is None for b in todays):
        return DayStatus("TEMPORARY", set())
    if wd in recurring_off_days:
        opens = [b for b in todays if b.kind == BlockKind.OPEN.value]
        if not opens:
            return DayStatus("RECURRING", set())
        if any(b.time_slot_id is None for b in opens):
            return DayStatus(None, base - closed)
        return DayStatus(None, (base & {b.time_slot_id for b in opens}) - closed)
    return DayStatus(None, base - closed)


def _date_range_inclusive(start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


class CalendarRepository:
    """강사 캘린더·반복 시간 슬롯·가용 시간 계산"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 캘린더 ────────────────────────────────────────────────────────────────

    async def get_by_host(self, host_id: UUID) -> Calendar:
        calendar = (await self.session.execute(select(Calendar).where(Calendar.host_id == host_id))).scalar_one_or_none()
        if not calendar:
            raise HTTPException(status_code=404, detail="Calendar not found")
        return calendar

    async def calendar_id_of_host(self, host_id: UUID) -> int:
        cal_id = (await self.session.execute(select(Calendar.id).where(Calendar.host_id == host_id))).scalar_one_or_none()
        if cal_id is None:
            raise HTTPException(status_code=404, detail="Calendar not found")
        return cal_id

    async def ensure_default(self, host_id: UUID) -> Calendar:
        """강사 캘린더가 없으면 만들고, 슬롯이 하나도 없으면 기본 슬롯(매일 07~20시, 1시간)을 만든다.
        강사 승인·강사 계정 생성 때 호출 (commit 포함)"""
        calendar = (await self.session.execute(select(Calendar).where(Calendar.host_id == host_id))).scalar_one_or_none()
        if calendar is None:
            calendar = Calendar(host_id=host_id, topics=[], description="")
            self.session.add(calendar)
            await self.session.flush()
        has_slot = (await self.session.execute(select(TimeSlot.id).where(TimeSlot.calendar_id == calendar.id).limit(1))).first()
        if has_slot is None:
            for h in DEFAULT_SLOT_HOURS:
                self.session.add(
                    TimeSlot(calendar_id=calendar.id, start_time=time(h), end_time=time(h + 1), weekdays=ALL_WEEKDAYS, is_active=True)
                )
        await self.session.commit()
        await self.session.refresh(calendar)
        return calendar

    async def create(self, host_id: UUID, data: CalendarCreate) -> Calendar:
        exists = await self.session.execute(select(Calendar).where(Calendar.host_id == host_id))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Calendar already exists for this host")
        calendar = Calendar(host_id=host_id, topics=data.topics, description=data.description)
        self.session.add(calendar)
        await self.session.commit()
        await self.session.refresh(calendar)
        return calendar

    async def update(self, host_id: UUID, data: CalendarUpdate) -> Calendar:
        calendar = await self.get_by_host(host_id)
        payload = data.model_dump(exclude_unset=True)
        if "topics" in payload:
            calendar.topics = payload["topics"]
        if "description" in payload:
            calendar.description = payload["description"]
        self.session.add(calendar)
        await self.session.commit()
        await self.session.refresh(calendar)
        return calendar

    # ── 반복 시간 슬롯 (전역 설정: 모든 날짜에 적용) ──────────────────────────

    async def list_slots(self, calendar_id: int, order_by_id: bool = True) -> list[TimeSlot]:
        stmt = select(TimeSlot).where(TimeSlot.calendar_id == calendar_id)
        if order_by_id:
            stmt = stmt.order_by(TimeSlot.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_slot(self, calendar_id: int, slot_id: int) -> TimeSlot:
        ts = (
            await self.session.execute(select(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.calendar_id == calendar_id))
        ).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="TimeSlot not found")
        return ts

    async def add_slot(self, calendar_id: int, data: TimeSlotCreate) -> TimeSlot:
        if data.end_time <= data.start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")
        if any((w < 0 or w > 6) for w in data.weekdays):
            raise HTTPException(status_code=400, detail="weekdays must be within 0..6")
        ts = TimeSlot(calendar_id=calendar_id, start_time=data.start_time, end_time=data.end_time, weekdays=data.weekdays)
        self.session.add(ts)
        await self.session.commit()
        await self.session.refresh(ts)
        return ts

    async def update_slot(self, ts: TimeSlot, data: TimeSlotUpdate) -> TimeSlot:
        payload = data.model_dump(exclude_unset=True)
        if "start_time" in payload:
            ts.start_time = payload["start_time"]
        if "end_time" in payload:
            ts.end_time = payload["end_time"]
        if "weekdays" in payload:
            if any((w < 0 or w > 6) for w in (payload["weekdays"] or [])):
                raise HTTPException(status_code=400, detail="weekdays must be within 0..6")
            ts.weekdays = payload["weekdays"]
        if "is_active" in payload:
            ts.is_active = payload["is_active"]
        if ts.end_time <= ts.start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")
        self.session.add(ts)
        await self.session.commit()
        await self.session.refresh(ts)
        return ts

    async def update_slot_weekdays(self, host_id: UUID, slot_id: int, weekdays: list[int]) -> TimeSlot:
        slot = await self.session.scalar(
            select(TimeSlot)
            .join(Calendar, Calendar.id == TimeSlot.calendar_id)
            .where(TimeSlot.id == slot_id, Calendar.host_id == host_id)
        )
        if not slot:
            raise HTTPException(status_code=403, detail="You can update time slots only in your calendar")
        slot.weekdays = weekdays
        await self.session.commit()
        await self.session.refresh(slot)
        return slot

    # 예약이 한 건이라도 있으면 삭제하지 않는다 (FK 오류 대신 409)
    async def delete_slot(self, ts: TimeSlot) -> None:
        booked = await self.session.execute(select(Booking.id).where(Booking.time_slot_id == ts.id).limit(1))
        if booked.first():
            raise HTTPException(status_code=409, detail="TimeSlot has bookings and cannot be deleted")
        await self.session.delete(ts)
        await self.session.commit()

    # ── 가용 시간 ────────────────────────────────────────────────────────────

    async def availability(self, host_id: UUID, start: date, end: date) -> AvailabilityResponse:
        """기간 내 날짜별 예약 가능한 시간 (휴무 규칙은 day_status)
        - 휴무일은 slots 가 비고 off_type 으로 정기(RECURRING)·임시(TEMPORARY)를 구분 (is_holiday = 임시 휴무일)
        - 이미 레슨이 잡힌 시간과 같은 시작·끝 시간대는 제외, 같은 시간대 중복 슬롯은 하나만
        """
        if end < start:
            raise HTTPException(status_code=400, detail="end must be >= start")
        if (end - start).days > 90:
            raise HTTPException(status_code=400, detail="range is too large (max 90 days)")

        calendar_id = (await self.session.execute(select(Calendar.id).where(Calendar.host_id == host_id))).scalar_one_or_none()
        if calendar_id is None:
            raise HTTPException(status_code=404, detail="Calendar not found")

        host = (await self.session.execute(select(User).where(User.id == host_id))).scalar_one_or_none()
        recurring_off: set[int] = set(host.recurring_off_days or []) if host else set()
        slots = list(
            (await self.session.execute(select(TimeSlot).where(TimeSlot.calendar_id == calendar_id).order_by(TimeSlot.id.asc()))).scalars().all()
        )
        blocks = await CalendarBlockRepository(self.session).list_overlapping(calendar_id, start, end)
        booked = (
            await self.session.execute(
                select(Booking.time_slot_id, Booking.when, TimeSlot.start_time, TimeSlot.end_time)
                .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
                .where(
                    TimeSlot.calendar_id == calendar_id,
                    Booking.when >= start,
                    Booking.when <= end,
                    Booking.status != "CANCELLED",
                )
            )
        ).all()
        booked_slot_date = {(row[0], row[1]) for row in booked}
        booked_time_date = {(row[2], row[3], row[1]) for row in booked}

        days_out: list[AvailabilityDay] = []
        for d in _date_range_inclusive(start, end):
            st = day_status(d, slots, recurring_off, blocks)
            day_slots: list[AvailabilitySlot] = []
            seen_times: set[tuple] = set()
            for s in slots:
                if s.id not in st.open_slot_ids or (s.id, d) in booked_slot_date:
                    continue
                if (s.start_time, s.end_time, d) in booked_time_date:
                    continue
                time_key = (s.start_time, s.end_time)
                if time_key in seen_times:
                    continue
                seen_times.add(time_key)
                day_slots.append(AvailabilitySlot(time_slot_id=s.id, start_time=s.start_time, end_time=s.end_time))
            days_out.append(
                AvailabilityDay(date=d, slots=day_slots, is_holiday=st.off_type == "TEMPORARY", off_type=st.off_type)
            )

        return AvailabilityResponse(host_id=host_id, start=start, end=end, days=days_out)


class CalendarBlockRepository:
    """특정 날짜에만 적용되는 예외 (임시 휴무일·시간 휴무·정기 휴무일 열기)

    매주 반복 설정(슬롯 요일, TimeSlot.is_active, 정기 휴무 요일)은 모든 날짜에 적용되는 전역 설정이다.
    "이 날짜만"의 조치는 반드시 이 블록으로 기록한다 (CLAUDE.md 상태 변경 범위 원칙).
    - CLOSE + 시간 없음: 임시 휴무일 (정기 휴무일이 아닌 날만)
    - CLOSE + 시간: 그날 그 시간만 휴무
    - OPEN  + 시간 없음/시간: 정기 휴무일 중 그날(그 시간)만 영업
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calendar_of_host(self, host_id: UUID) -> Calendar:
        calendar = (await self.session.execute(select(Calendar).where(Calendar.host_id == host_id))).scalar_one_or_none()
        if calendar is None:
            raise HTTPException(status_code=404, detail="Calendar not found")
        return calendar

    async def calendar_id_of_host(self, host_id: UUID) -> int:
        return (await self.calendar_of_host(host_id)).id

    # ── 조회 ──────────────────────────────────────────────────────────────────

    async def list_overlapping(self, calendar_id: int, start: date, end: date) -> list[CalendarBlock]:
        res = await self.session.execute(
            select(CalendarBlock)
            .where(
                CalendarBlock.calendar_id == calendar_id,
                CalendarBlock.start_date <= end,
                CalendarBlock.end_date >= start,
            )
            .order_by(CalendarBlock.start_date, CalendarBlock.kind, CalendarBlock.time_slot_id, CalendarBlock.id)
        )
        return list(res.scalars().all())

    async def _recurring_off_days(self, calendar: Calendar) -> set[int]:
        host = await self.session.get(User, calendar.host_id)
        return set(host.recurring_off_days or []) if host else set()

    async def day_status_for(self, calendar: Calendar, day: date) -> DayStatus:
        slots = list((await self.session.execute(select(TimeSlot).where(TimeSlot.calendar_id == calendar.id))).scalars().all())
        return day_status(day, slots, await self._recurring_off_days(calendar), await self.list_overlapping(calendar.id, day, day))

    async def _has_active_lesson(self, calendar_id: int, day: date, slot_ids: Optional[list[int]]) -> bool:
        q = (
            select(Booking.id)
            .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
            .where(
                TimeSlot.calendar_id == calendar_id,
                Booking.when == day,
                Booking.type == BookingType.LESSON,
                Booking.status.in_(ACTIVE_LESSON_STATUSES),
            )
        )
        if slot_ids:
            q = q.where(Booking.time_slot_id.in_(slot_ids))
        return (await self.session.execute(q.limit(1))).first() is not None

    # ── 생성·삭제 ─────────────────────────────────────────────────────────────

    async def create_for_date(
        self, calendar: Calendar, day: date, time_slot_ids: list[int], reason: Optional[str], kind: str = BlockKind.CLOSE.value
    ) -> list[CalendarBlock]:
        if day < date.today():
            raise HTTPException(status_code=400, detail="지난 날짜는 바꿀 수 없습니다.")

        slot_ids = sorted(set(time_slot_ids))
        if slot_ids:
            owned = set(
                (await self.session.execute(
                    select(TimeSlot.id).where(TimeSlot.id.in_(slot_ids), TimeSlot.calendar_id == calendar.id)
                )).scalars().all()
            )
            if owned != set(slot_ids):
                raise HTTPException(status_code=404, detail="TimeSlot not found")

        recurring = day.weekday() in await self._recurring_off_days(calendar)
        if kind == BlockKind.OPEN.value:
            if not recurring:
                raise HTTPException(status_code=400, detail="정기 휴무일에만 특정 날짜를 열 수 있습니다.")
        else:
            if recurring and not slot_ids:
                raise HTTPException(status_code=400, detail="정기 휴무일은 이미 휴무입니다.")
            # 이미 잡힌 레슨이 있는 시간은 닫지 않는다 (예약을 먼저 처리해야 함)
            if await self._has_active_lesson(calendar.id, day, slot_ids):
                raise HTTPException(status_code=409, detail="예약이 있는 시간은 닫을 수 없습니다. 예약을 먼저 처리하세요.")

        # 같은 날짜·종류·시간 블록이 이미 있으면 그대로 둔다 (중복 생성 방지)
        existing = {
            (b.kind, b.time_slot_id): b
            for b in await self.list_overlapping(calendar.id, day, day)
            if b.start_date == day and b.end_date == day
        }
        result: list[CalendarBlock] = []
        for slot_id in (slot_ids or [None]):
            if (kind, slot_id) in existing:
                result.append(existing[(kind, slot_id)])
                continue
            block = CalendarBlock(
                calendar_id=calendar.id, start_date=day, end_date=day, time_slot_id=slot_id, reason=reason, kind=kind
            )
            self.session.add(block)
            result.append(block)

        await self.session.commit()
        for b in result:
            await self.session.refresh(b)
        return result

    async def delete(self, calendar_id: int, block_id: int) -> None:
        """블록 해제. 정기 휴무일을 열어 둔 것(OPEN)을 해제하면 그 시간이 다시 닫히므로, 그 시간에 레슨이 있으면 막는다"""
        block = await self.session.get(CalendarBlock, block_id)
        if not block or block.calendar_id != calendar_id:
            raise HTTPException(status_code=404, detail="Block not found")
        await self.session.delete(block)
        if block.kind == BlockKind.OPEN.value:
            # 해제한 뒤에도 그날 잡힌 레슨 시간이 모두 열려 있어야 한다 (다른 OPEN 블록이 덮고 있으면 허용)
            await self.session.flush()
            calendar = await self.session.get(Calendar, calendar_id)
            st = await self.day_status_for(calendar, block.start_date)
            lesson_slots = set(
                (await self.session.execute(
                    select(Booking.time_slot_id)
                    .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
                    .where(
                        TimeSlot.calendar_id == calendar_id,
                        Booking.when == block.start_date,
                        Booking.status.in_(ACTIVE_LESSON_STATUSES),
                    )
                )).scalars().all()
            )
            if lesson_slots - st.open_slot_ids:
                await self.session.rollback()
                raise HTTPException(status_code=409, detail="열어 둔 시간에 예약이 있어 다시 닫을 수 없습니다. 예약을 먼저 처리하세요.")
        await self.session.commit()
