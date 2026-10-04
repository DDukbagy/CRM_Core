from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.lesson_notes.repository import LessonNoteRepository
from app.domains.lesson_notes.schemas import (
    LessonNoteCreate,
    LessonNoteRead,
    LessonNoteUpdate,
    LessonNoteUploadRequest,
    LessonNoteUploadResponse,
)

router = APIRouter(prefix="/lesson-notes", tags=["LessonNote"])
WRITERS = {"INSTRUCTOR", "ADMIN"}


@router.post("", response_model=LessonNoteRead, status_code=status.HTTP_201_CREATED)
async def create_lesson_note(
    data: LessonNoteCreate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role(WRITERS)),
):
    """강사가 담당 고객에게 레슨 노트 작성 (글 또는 스캔 PDF, 예약 연결은 선택)."""
    repo = LessonNoteRepository(session)
    return await repo.to_read(await repo.create(data, instructor))


@router.get("", response_model=list[LessonNoteRead])
async def list_lesson_notes(
    customer_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """강사: 내가 쓴 노트(customer_id 로 고객별) / 고객: 나에게 공유된 노트."""
    repo = LessonNoteRepository(session)
    return [await repo.to_read(n) for n in await repo.list_for(user, customer_id)]


@router.post("/upload-url", response_model=LessonNoteUploadResponse)
async def get_lesson_note_upload_url(
    req: LessonNoteUploadRequest,
    instructor: CurrentUser = Depends(require_role(WRITERS)),
):
    """스캔한 노트 PDF 업로드용 서명 주소."""
    url, key = LessonNoteRepository.upload_url(instructor, req.filename, req.content_type)
    return LessonNoteUploadResponse(upload_url=url, key=key)


@router.get("/booking/{booking_id}", response_model=LessonNoteRead)
async def get_lesson_note(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """예약에 연결된 레슨 노트 조회 (고객은 공유된 노트만)."""
    repo = LessonNoteRepository(session)
    note = await repo.get_by_booking_or_404(booking_id)
    await repo.ensure_can_view(note, user)
    return await repo.to_read(note)


@router.patch("/booking/{booking_id}", response_model=LessonNoteRead)
async def update_lesson_note(
    booking_id: int,
    data: LessonNoteUpdate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role(WRITERS)),
):
    """예약에 연결된 레슨 노트 수정."""
    repo = LessonNoteRepository(session)
    return await repo.to_read(await repo.update(await repo.get_by_booking_or_404(booking_id), data, instructor))


@router.get("/{note_id}", response_model=LessonNoteRead)
async def get_lesson_note_by_id(
    note_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = LessonNoteRepository(session)
    note = await repo.get_or_404(note_id)
    await repo.ensure_can_view(note, user)
    return await repo.to_read(note)


@router.patch("/{note_id}", response_model=LessonNoteRead)
async def update_lesson_note_by_id(
    note_id: UUID,
    data: LessonNoteUpdate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role(WRITERS)),
):
    repo = LessonNoteRepository(session)
    return await repo.to_read(await repo.update(await repo.get_or_404(note_id), data, instructor))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_note(
    note_id: UUID,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role(WRITERS)),
):
    repo = LessonNoteRepository(session)
    await repo.delete(await repo.get_or_404(note_id), instructor)
    return None
