from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import (
    BookingCancelRequest,
    BookingCancelResponse,
    BookingConfirmRequest,
    BookingCreate,
    BookingRead,
    BookingUpdateRequest,
)
from app.domains.calendar.repository import CalendarRepository

# 경로는 분리 전과 같다: 강사 쪽은 /calendars/me/bookings..., 고객 쪽은 /bookings...
router = APIRouter()
cal_router = APIRouter(prefix="/calendars", tags=["Booking"])
bk_router = APIRouter(prefix="/bookings", tags=["Booking"])

HOST_ROLES = {"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"}
INSTRUCTOR_ROLES = {"INSTRUCTOR", "ADMIN"}


def _cancel_response(booking) -> BookingCancelResponse:
    return BookingCancelResponse(id=booking.id, status=booking.status, cancel_reason=booking.cancel_reason, updated_at=booking.updated_at)


def _reason(body: BookingCancelRequest | None) -> str | None:
    return body.reason if body is not None else None


# --- Host: 예약 목록 ---
@cal_router.get("/me/bookings", response_model=list[BookingRead])
async def list_my_calendar_bookings(
    start: date = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end: date = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")
    calendar_id = await CalendarRepository(session).calendar_id_of_host(UUID(str(host.id)))
    return await BookingRepository(session).list_by_calendar(calendar_id, start, end)


# --- Bookings: 생성·조회 ---
@bk_router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """LESSON: 고객 신청(REQUESTED) / HOLIDAY·WORK_OVERRIDE: 그 캘린더의 강사만(CONFIRMED)"""
    return await BookingRepository(session).create(data, user)


@bk_router.get("/me", response_model=list[BookingRead])
async def list_my_bookings(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    return await BookingRepository(session).list_by_guest(UUID(str(user.id)))


# --- Host: 예약 상태 전환 ---
@cal_router.patch("/me/bookings/{booking_id}/confirm", response_model=BookingRead)
async def confirm_booking_as_host(
    booking_id: int,
    body: BookingConfirmRequest | None = None,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """확정: REQUESTED -> CONFIRMED"""
    repo = BookingRepository(session)
    return await repo.confirm(await repo.get_or_404(booking_id), host, body.topic if body else None)


@cal_router.patch("/me/bookings/{booking_id}/decline", response_model=BookingRead)
async def decline_booking_as_host(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """거절: REQUESTED -> CANCELLED (슬롯 다시 열림)"""
    repo = BookingRepository(session)
    return await repo.decline(await repo.get_or_404(booking_id), host, _reason(body))


@cal_router.patch("/me/bookings/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_host(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(HOST_ROLES)),
):
    """강사 취소: CONFIRMED -> CANCELLED (휴무·영업일 전환 해제 포함). 신청 중은 decline"""
    repo = BookingRepository(session)
    return _cancel_response(await repo.cancel_by_host(await repo.get_or_404(booking_id), host, _reason(body)))


@cal_router.patch("/me/bookings/{booking_id}/complete", response_model=BookingRead)
async def complete_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """출석 완료: CONFIRMED -> COMPLETED (수강권·TIMES 멤버십 1회 차감)"""
    repo = BookingRepository(session)
    return await repo.complete(await repo.get_or_404(booking_id), host)


@cal_router.patch("/me/bookings/{booking_id}/no-show", response_model=BookingRead)
async def no_show_booking_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """노쇼: CONFIRMED -> NO_SHOW (수강권 차감)"""
    repo = BookingRepository(session)
    return await repo.mark_no_show(await repo.get_or_404(booking_id), host)


@cal_router.patch("/me/bookings/{booking_id}/approve-cancel", response_model=BookingCancelResponse)
async def approve_cancel_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """고객 취소 신청 승인: CANCEL_REQUESTED -> CANCELLED"""
    repo = BookingRepository(session)
    return _cancel_response(await repo.approve_cancel(await repo.get_or_404(booking_id), host))


@cal_router.patch("/me/bookings/{booking_id}/reject-cancel", response_model=BookingRead)
async def reject_cancel_as_host(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    host: CurrentUser = Depends(require_role(INSTRUCTOR_ROLES)),
):
    """고객 취소 신청 거절: CANCEL_REQUESTED -> CONFIRMED"""
    repo = BookingRepository(session)
    return await repo.reject_cancel(await repo.get_or_404(booking_id), host)


# --- Guest: 예약 상태 전환 ---
@bk_router.patch("/{booking_id}", response_model=BookingRead)
async def update_booking_as_guest(
    booking_id: int,
    body: BookingUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER", "ADMIN"})),
):
    """REQUESTED 상태인 예약의 주제/메모를 수정합니다."""
    repo = BookingRepository(session)
    return await repo.update_by_guest(
        await repo.get_or_404(booking_id), user, body.topic, "description" in body.model_fields_set, body.description
    )


@bk_router.patch("/{booking_id}/cancel", response_model=BookingCancelResponse)
async def cancel_booking_as_guest(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객 취소 신청: CONFIRMED -> CANCEL_REQUESTED (강사 승인 대기). 신청 중은 withdraw"""
    repo = BookingRepository(session)
    return _cancel_response(await repo.request_cancel_by_guest(await repo.get_or_404(booking_id), user, _reason(body)))


@bk_router.patch("/{booking_id}/withdraw", response_model=BookingCancelResponse)
async def withdraw_booking_as_guest(
    booking_id: int,
    body: BookingCancelRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객 신청 철회: REQUESTED -> CANCELLED"""
    repo = BookingRepository(session)
    return _cancel_response(await repo.withdraw_by_guest(await repo.get_or_404(booking_id), user, _reason(body)))


@bk_router.patch("/{booking_id}/withdraw-cancel", response_model=BookingRead)
async def withdraw_cancel_as_guest(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객 취소 신청 철회: CANCEL_REQUESTED -> CONFIRMED (강사 승인 전)"""
    repo = BookingRepository(session)
    return await repo.withdraw_cancel_by_guest(await repo.get_or_404(booking_id), user)


# 스마트폰 캘린더용 .ics 파일 다운로드 (예약한 고객·강사·관리자만)
@bk_router.get("/{booking_id}/download", summary="스마트폰 캘린더 연동 (.ics 다운로드)")
async def download_booking_ics(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = BookingRepository(session)
    content = await repo.ics_for(await repo.get_or_404(booking_id), user)
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=booking_{booking_id}.ics"},
    )


router.include_router(cal_router)
router.include_router(bk_router)
