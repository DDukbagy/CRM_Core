from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.domains.booking.models import Booking
from app.domains.calendar.models import Calendar, TimeSlot
from app.domains.lesson_notes.models import LessonNote
from app.domains.lesson_notes.schemas import LessonNoteCreate, LessonNoteUpdate


class LessonNoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_booking_or_404(self, booking_id: int) -> LessonNote:
        note = (
            await self.session.execute(select(LessonNote).where(LessonNote.booking_id == booking_id))
        ).scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Lesson note not found")
        return note

    # 강사는 본인 캘린더의 확정·완료 예약에만, 예약당 하나
    async def create(self, data: LessonNoteCreate, instructor: CurrentUser) -> LessonNote:
        instructor_id = UUID(str(instructor.id))

        booking = (await self.session.execute(select(Booking).where(Booking.id == data.booking_id))).scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if instructor.role != "ADMIN":
            host_id = (
                await self.session.execute(
                    select(Calendar.host_id)
                    .join(TimeSlot, TimeSlot.calendar_id == Calendar.id)
                    .where(TimeSlot.id == booking.time_slot_id)
                )
            ).scalar_one_or_none()
            if host_id != instructor_id:
                raise HTTPException(status_code=403, detail="본인 캘린더의 예약에만 노트를 작성할 수 있습니다.")

        if booking.status not in ("CONFIRMED", "COMPLETED"):
            raise HTTPException(status_code=400, detail="레슨 노트는 확정/완료 예약에만 작성 가능합니다.")

        existing = await self.session.execute(select(LessonNote).where(LessonNote.booking_id == data.booking_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="이미 이 예약에 노트가 존재합니다. PATCH로 수정하세요.")

        note = LessonNote(
            booking_id=data.booking_id, instructor_id=instructor_id, content=data.content, is_shared=data.is_shared
        )
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note

    # 강사 본인·관리자는 전체, 고객은 그 예약의 게스트이고 공유된 노트만
    async def ensure_can_view(self, note: LessonNote, booking_id: int, user: CurrentUser) -> None:
        user_id = UUID(str(user.id))
        if user.role in ("INSTRUCTOR", "ADMIN"):
            if user.role == "INSTRUCTOR" and note.instructor_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
            return
        booking = (await self.session.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if not booking or booking.guest_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not note.is_shared:
            raise HTTPException(status_code=403, detail="강사가 아직 공유하지 않은 노트입니다.")

    async def update(self, note: LessonNote, data: LessonNoteUpdate, instructor: CurrentUser) -> LessonNote:
        if instructor.role == "INSTRUCTOR" and note.instructor_id != UUID(str(instructor.id)):
            raise HTTPException(status_code=403, detail="Forbidden")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(note, field, value)
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note
