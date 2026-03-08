from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.calendar.lesson_note_models import LessonNote
from app.domains.calendar.models import Booking

router = APIRouter(prefix="/lesson-notes", tags=["LessonNote"])


class LessonNoteCreate(BaseModel):
    booking_id: int
    content: str
    is_shared: bool = False
    model_config = ConfigDict(extra="forbid")


class LessonNoteUpdate(BaseModel):
    content: str | None = None
    is_shared: bool | None = None
    model_config = ConfigDict(extra="forbid")


class LessonNoteRead(BaseModel):
    id: UUID
    booking_id: int
    instructor_id: UUID
    content: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=LessonNoteRead, status_code=status.HTTP_201_CREATED)
async def create_lesson_note(
    data: LessonNoteCreate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 완료된/확정된 레슨에 노트를 작성합니다."""
    instructor_id = UUID(str(instructor.id))

    bk_res = await session.execute(select(Booking).where(Booking.id == data.booking_id))
    booking = bk_res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status not in ("CONFIRMED", "COMPLETED"):
        raise HTTPException(status_code=400, detail="레슨 노트는 확정/완료 예약에만 작성 가능합니다.")

    # 중복 확인
    existing_res = await session.execute(
        select(LessonNote).where(LessonNote.booking_id == data.booking_id)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 이 예약에 노트가 존재합니다. PATCH로 수정하세요.")

    note = LessonNote(
        booking_id=data.booking_id,
        instructor_id=instructor_id,
        content=data.content,
        is_shared=data.is_shared,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


@router.get("/booking/{booking_id}", response_model=LessonNoteRead)
async def get_lesson_note(
    booking_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """예약에 연결된 레슨 노트 조회."""
    user_id = UUID(str(user.id))

    res = await session.execute(
        select(LessonNote).where(LessonNote.booking_id == booking_id)
    )
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lesson note not found")

    # 권한: 강사 본인 or ADMIN → 전체 조회 / 고객 → is_shared만
    if user.role in ("INSTRUCTOR", "ADMIN"):
        if user.role == "INSTRUCTOR" and note.instructor_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        # 고객: 해당 예약의 게스트이고 is_shared=True인 경우만
        bk_res = await session.execute(select(Booking).where(Booking.id == booking_id))
        booking = bk_res.scalar_one_or_none()
        if not booking or booking.guest_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not note.is_shared:
            raise HTTPException(status_code=403, detail="강사가 아직 공유하지 않은 노트입니다.")

    return note


@router.patch("/booking/{booking_id}", response_model=LessonNoteRead)
async def update_lesson_note(
    booking_id: int,
    data: LessonNoteUpdate,
    session: AsyncSession = Depends(get_session),
    instructor: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """레슨 노트 수정."""
    instructor_id = UUID(str(instructor.id))

    res = await session.execute(
        select(LessonNote).where(LessonNote.booking_id == booking_id)
    )
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lesson note not found")

    if instructor.role == "INSTRUCTOR" and note.instructor_id != instructor_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(note, field, value)

    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note
