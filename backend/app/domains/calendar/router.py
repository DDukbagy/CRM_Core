from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.calendar.repository import CalendarBlockRepository, CalendarRepository
from app.domains.calendar.schemas import (
    AvailabilityResponse,
    CalendarCreate,
    CalendarRead,
    CalendarUpdate,
    TimeSlotCreate,
    TimeSlotRead,
    TimeSlotUpdate,
    TimeSlotWeekdaysPatch,
    CalendarBlockCreate,
    CalendarBlockRead,
)

router = APIRouter()
cal_router = APIRouter(prefix="/calendars", tags=["Calendar"])

HOST_ROLES = {"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"}


# --- Host: My Calendar ---
@cal_router.post("/me", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
async def create_my_calendar(
    data: CalendarCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    return await CalendarRepository(session).create(UUID(str(host.id)), data)


@cal_router.get("/me", response_model=CalendarRead)
async def get_my_calendar(
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    return await CalendarRepository(session).get_by_host(UUID(str(host.id)))


@cal_router.patch("/me", response_model=CalendarRead)
async def update_my_calendar(
    data: CalendarUpdate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    return await CalendarRepository(session).update(UUID(str(host.id)), data)


# --- Host: TimeSlots CRUD (전역 설정 — 모든 날짜에 적용) ---
@cal_router.post("/me/time-slots", response_model=TimeSlotRead, status_code=status.HTTP_201_CREATED)
async def add_time_slot(
    data: TimeSlotCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    repo = CalendarRepository(session)
    calendar_id = await repo.calendar_id_of_host(UUID(str(host.id)))
    return await repo.add_slot(calendar_id, data)


@cal_router.get("/me/time-slots", response_model=list[TimeSlotRead])
async def list_my_time_slots(
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    repo = CalendarRepository(session)
    return await repo.list_slots(await repo.calendar_id_of_host(UUID(str(host.id))))


@cal_router.patch("/me/time-slots/{slot_id}", response_model=TimeSlotRead)
async def update_time_slot(
    slot_id: int,
    data: TimeSlotUpdate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    repo = CalendarRepository(session)
    ts = await repo.get_slot(await repo.calendar_id_of_host(UUID(str(host.id))), slot_id)
    return await repo.update_slot(ts, data)


@cal_router.delete("/me/time-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_slot(
    slot_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    """예약이 하나도 없는 슬롯만 삭제 (있으면 409)"""
    repo = CalendarRepository(session)
    ts = await repo.get_slot(await repo.calendar_id_of_host(UUID(str(host.id))), slot_id)
    await repo.delete_slot(ts)
    return None


# --- 날짜별 예외: 임시 휴무일·시간 휴무(CLOSE), 정기 휴무일 열기(OPEN) — 슬롯 자체(is_active)는 바꾸지 않는다 ---
@cal_router.get("/me/blocks", response_model=list[CalendarBlockRead])
async def list_my_blocks(
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")
    repo = CalendarBlockRepository(session)
    calendar_id = await repo.calendar_id_of_host(UUID(str(host.id)))
    return await repo.list_overlapping(calendar_id, start, end)


@cal_router.post("/me/blocks", response_model=list[CalendarBlockRead], status_code=status.HTTP_201_CREATED)
async def create_my_blocks(
    data: CalendarBlockCreate,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    repo = CalendarBlockRepository(session)
    calendar = await repo.calendar_of_host(UUID(str(host.id)))
    return await repo.create_for_date(calendar, data.date, data.time_slot_ids, data.reason, data.kind)


@cal_router.delete("/me/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_block(
    block_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    repo = CalendarBlockRepository(session)
    calendar_id = await repo.calendar_id_of_host(UUID(str(host.id)))
    await repo.delete(calendar_id, block_id)
    return None


# --- Public: Host Calendar & Availability ---
@cal_router.get("/{host_id}", response_model=CalendarRead)
async def get_host_calendar(
    host_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await CalendarRepository(session).get_by_host(host_id)


@cal_router.get("/{host_id}/time-slots", response_model=list[TimeSlotRead])
async def get_host_time_slots(
    host_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """강사의 타임슬롯 목록 조회 (고객이 과거 예약 시간 표시에 사용)"""
    repo = CalendarRepository(session)
    calendar = await repo.get_by_host(host_id)
    return await repo.list_slots(calendar.id, order_by_id=False)


@cal_router.get("/{host_id}/availability", response_model=AvailabilityResponse)
async def get_availability(
    host_id: UUID,
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    return await CalendarRepository(session).availability(host_id, start, end)


@router.patch("/calendars/me/time-slots/{time_slot_id}/weekdays")
async def patch_my_time_slot_weekdays(
    time_slot_id: int,
    body: TimeSlotWeekdaysPatch,
    session: AsyncSession = Depends(get_session),
    me: CurrentUser = Depends(get_current_user),
):
    """내 캘린더(= calendars.host_id == me.id)에 속한 time_slot만 수정 가능"""
    slot = await CalendarRepository(session).update_slot_weekdays(UUID(str(me.id)), time_slot_id, body.weekdays)
    return {"id": slot.id, "calendar_id": slot.calendar_id, "weekdays": slot.weekdays}


router.include_router(cal_router)
