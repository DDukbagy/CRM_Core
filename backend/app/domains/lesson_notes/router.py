from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.lesson_notes.repository import LessonNoteRepository
from app.domains.lesson_notes.schemas import LessonNoteCreate, LessonNoteRead, LessonNoteUpdate

router = APIRouter(prefix="/lesson-notes", tags=["LessonNote"])


@router.post("", response_model=LessonNoteRead, status_code=status.HTTP_201_CREATED)
async def create_lesson_note(
    data: LessonNoteCreate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 본인 캘린더의 확정/완료 레슨에 노트를 작성합니다."""
    return await LessonNoteRepository(session).create(data, instructor)


@router.get("/booking/{booking_id}", response_model=LessonNoteRead)
async def get_lesson_note(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """예약에 연결된 레슨 노트 조회 (고객은 공유된 노트만)."""
    repo = LessonNoteRepository(session)
    note = await repo.get_by_booking_or_404(booking_id)
    await repo.ensure_can_view(note, booking_id, user)
    return note


@router.patch("/booking/{booking_id}", response_model=LessonNoteRead)
async def update_lesson_note(
    booking_id: int,
    data: LessonNoteUpdate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """레슨 노트 수정."""
    repo = LessonNoteRepository(session)
    return await repo.update(await repo.get_by_booking_or_404(booking_id), data, instructor)
