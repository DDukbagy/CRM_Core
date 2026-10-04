import uuid as _uuid
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.core.s3 import create_presigned_upload_url, create_presigned_url, delete_file_from_s3
from app.domains.booking.models import Booking
from app.domains.calendar.models import Calendar, TimeSlot
from app.domains.lesson_notes.models import LessonNote
from app.domains.lesson_notes.schemas import LessonNoteCreate, LessonNoteRead, LessonNoteUpdate
from app.domains.users.models import User

ALLOWED_FILE_TYPES = {"application/pdf"}


class LessonNoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 조회 ──────────────────────────────────────────────────────────────────

    async def get_or_404(self, note_id: UUID) -> LessonNote:
        note = await self.session.get(LessonNote, note_id)
        if not note:
            raise HTTPException(status_code=404, detail="Lesson note not found")
        return note

    async def get_by_booking_or_404(self, booking_id: int) -> LessonNote:
        note = (
            await self.session.execute(select(LessonNote).where(LessonNote.booking_id == booking_id))
        ).scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Lesson note not found")
        return note

    async def list_for(self, user: CurrentUser, customer_id: Optional[UUID]) -> list[LessonNote]:
        """강사: 내가 쓴 노트(고객별 필터) / 고객: 나에게 공유된 노트 / 관리자: 전체"""
        uid = UUID(str(user.id))
        q = select(LessonNote)
        if user.role == "CUSTOMER":
            q = q.where(LessonNote.customer_id == uid, LessonNote.is_shared == True)  # noqa: E712
        elif user.role == "INSTRUCTOR":
            q = q.where(LessonNote.instructor_id == uid)
        if customer_id is not None and user.role != "CUSTOMER":
            q = q.where(LessonNote.customer_id == customer_id)
        return list((await self.session.execute(q.order_by(LessonNote.created_at.desc()))).scalars().all())

    # 강사 본인·관리자는 전체, 고객은 자기 노트 중 공유된 것만
    async def ensure_can_view(self, note: LessonNote, user: CurrentUser) -> None:
        uid = UUID(str(user.id))
        if user.role == "ADMIN":
            return
        if user.role == "INSTRUCTOR":
            if note.instructor_id != uid:
                raise HTTPException(status_code=403, detail="Forbidden")
            return
        if note.customer_id != uid:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not note.is_shared:
            raise HTTPException(status_code=403, detail="강사가 아직 공유하지 않은 노트입니다.")

    async def to_read(self, note: LessonNote) -> LessonNoteRead:
        names = {}
        for uid in {note.customer_id, note.instructor_id}:
            u = await self.session.get(User, uid)
            names[uid] = u.display_name if u else None
        read = LessonNoteRead.model_validate(note)
        read.customer_name = names.get(note.customer_id)
        read.instructor_name = names.get(note.instructor_id)
        read.file_url = create_presigned_url(note.file_key) if note.file_key else None
        return read

    # ── 작성·수정·삭제 ────────────────────────────────────────────────────────

    async def _host_of_booking(self, booking: Booking) -> Optional[UUID]:
        return (
            await self.session.execute(
                select(Calendar.host_id).join(TimeSlot, TimeSlot.calendar_id == Calendar.id).where(TimeSlot.id == booking.time_slot_id)
            )
        ).scalar_one_or_none()

    async def create(self, data: LessonNoteCreate, instructor: CurrentUser) -> LessonNote:
        """강사는 담당 고객에게(예약에 연결하면 본인 캘린더의 확정·완료 예약만, 예약당 하나)"""
        instructor_id = UUID(str(instructor.id))
        is_admin = instructor.role == "ADMIN"
        if not (data.content and data.content.strip()) and not data.file_key:
            raise HTTPException(status_code=400, detail="내용을 입력하거나 PDF 를 첨부하세요.")

        customer_id = data.customer_id
        if data.booking_id is not None:
            booking = await self.session.get(Booking, data.booking_id)
            if not booking:
                raise HTTPException(status_code=404, detail="Booking not found")
            if not is_admin and await self._host_of_booking(booking) != instructor_id:
                raise HTTPException(status_code=403, detail="본인 캘린더의 예약에만 노트를 작성할 수 있습니다.")
            if booking.status not in ("CONFIRMED", "COMPLETED"):
                raise HTTPException(status_code=400, detail="레슨 노트는 확정/완료 예약에만 작성 가능합니다.")
            if customer_id is not None and customer_id != booking.guest_id:
                raise HTTPException(status_code=400, detail="예약의 고객과 다릅니다.")
            customer_id = booking.guest_id
            existing = await self.session.execute(select(LessonNote).where(LessonNote.booking_id == data.booking_id))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="이미 이 예약에 노트가 존재합니다. PATCH로 수정하세요.")
        elif customer_id is None:
            raise HTTPException(status_code=400, detail="고객(customer_id) 또는 예약(booking_id)을 지정하세요.")
        else:
            customer = await self.session.get(User, customer_id)
            if not customer or (customer.role or "").upper() != "CUSTOMER":
                raise HTTPException(status_code=404, detail="Customer not found")
            if not is_admin and customer.manager_id != instructor_id:
                raise HTTPException(status_code=403, detail="담당 고객에게만 노트를 작성할 수 있습니다.")

        self._check_file_key(data.file_key, instructor_id, is_admin)
        note = LessonNote(
            customer_id=customer_id, booking_id=data.booking_id, instructor_id=instructor_id,
            title=data.title, content=(data.content or None), file_key=data.file_key, file_name=data.file_name,
            is_shared=data.is_shared,
        )
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note

    def _check_file_key(self, key: Optional[str], instructor_id: UUID, is_admin: bool) -> None:
        """다른 강사가 올린 파일을 끌어다 붙이지 못하게: 업로드 주소를 받은 본인 경로만"""
        if key and not is_admin and not key.startswith(f"lesson-notes/{instructor_id}/"):
            raise HTTPException(status_code=400, detail="잘못된 파일입니다.")

    def _ensure_author(self, note: LessonNote, user: CurrentUser) -> None:
        if user.role != "ADMIN" and note.instructor_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")

    async def update(self, note: LessonNote, data: LessonNoteUpdate, instructor: CurrentUser) -> LessonNote:
        self._ensure_author(note, instructor)
        changes = data.model_dump(exclude_unset=True)
        self._check_file_key(changes.get("file_key"), UUID(str(instructor.id)), instructor.role == "ADMIN")
        old_key = note.file_key
        for field, value in changes.items():
            setattr(note, field, value)
        if not (note.content and note.content.strip()) and not note.file_key:
            raise HTTPException(status_code=400, detail="내용을 입력하거나 PDF 를 첨부하세요.")
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        if old_key and old_key != note.file_key:
            delete_file_from_s3(old_key)
        return note

    async def delete(self, note: LessonNote, instructor: CurrentUser) -> None:
        self._ensure_author(note, instructor)
        key = note.file_key
        await self.session.delete(note)
        await self.session.commit()
        if key:
            delete_file_from_s3(key)

    @staticmethod
    def upload_url(instructor: CurrentUser, filename: str, content_type: str) -> tuple[str, str]:
        """스캔한 노트(PDF) 업로드용 서명 주소 (S3 직접 PUT)"""
        if content_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(status_code=400, detail="PDF 파일만 올릴 수 있습니다.")
        key = f"lesson-notes/{instructor.id}/{_uuid.uuid4()}.pdf"
        url = create_presigned_upload_url(key, content_type)
        if not url:
            raise HTTPException(status_code=503, detail="파일 저장소(S3)가 설정되지 않았습니다.")
        return url, key
