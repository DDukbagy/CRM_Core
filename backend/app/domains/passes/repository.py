from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.core.retention import retention_cutoff
from app.domains.passes.models import CustomerPass, LessonPassType
from app.domains.passes.schemas import CustomerPassAssign, CustomerPassUpdate, PassTypeCreate, PassTypeUpdate
from app.domains.users.models import User


class PassRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 수강권 상품 (강사) ────────────────────────────────────────────────────

    async def list_types_of(self, instructor_id: UUID, active_only: bool = False) -> list[LessonPassType]:
        stmt = select(LessonPassType).where(LessonPassType.instructor_id == instructor_id)
        if active_only:
            stmt = stmt.where(LessonPassType.is_active == True).order_by(  # noqa: E712
                LessonPassType.duration_hours, LessonPassType.session_count
            )
        else:
            stmt = stmt.order_by(LessonPassType.duration_hours, LessonPassType.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_type(self, data: PassTypeCreate, instructor_id: UUID) -> LessonPassType:
        pt = LessonPassType(
            instructor_id=instructor_id,
            name=data.name,
            duration_hours=data.duration_hours,
            session_count=data.session_count,
            price=data.price,
            description=data.description,
        )
        self.session.add(pt)
        await self.session.commit()
        await self.session.refresh(pt)
        return pt

    async def get_own_type(self, pass_type_id: int, instructor_id: UUID) -> LessonPassType:
        pt = await self.session.get(LessonPassType, pass_type_id)
        if not pt:
            raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")
        if pt.instructor_id != instructor_id:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        return pt

    async def update_type(self, pt: LessonPassType, data: PassTypeUpdate) -> LessonPassType:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(pt, field, value)
        self.session.add(pt)
        await self.session.commit()
        await self.session.refresh(pt)
        return pt

    # 활성 고객 수강권이 있으면 삭제 대신 비활성화를 쓰게 한다
    async def delete_type(self, pt: LessonPassType) -> None:
        active = await self.session.execute(
            select(CustomerPass).where(CustomerPass.pass_type_id == pt.id, CustomerPass.status == "ACTIVE").limit(1)
        )
        if active.scalars().first():
            raise HTTPException(status_code=409, detail="활성 수강권이 있어 삭제할 수 없습니다. 비활성화를 사용하세요.")
        await self.session.delete(pt)
        await self.session.commit()

    # ── 고객 수강권 ──────────────────────────────────────────────────────────

    async def list_by_instructor(self, instructor_id: UUID) -> list[CustomerPass]:
        res = await self.session.execute(
            select(CustomerPass)
            .where(CustomerPass.instructor_id == instructor_id)
            .order_by(CustomerPass.status, CustomerPass.created_at.desc())
        )
        return list(res.scalars().all())

    async def list_by_customer(self, customer_id: UUID) -> list[CustomerPass]:
        res = await self.session.execute(
            select(CustomerPass)
            .where(CustomerPass.customer_id == customer_id)
            .order_by(CustomerPass.status, CustomerPass.created_at.desc())
        )
        return list(res.scalars().all())

    # 본인 상품을 활성 상태일 때만, 강사는 담당 고객에게만 발급. 상품 내용을 발급 시점 값으로 복사
    async def assign(self, data: CustomerPassAssign, user: CurrentUser) -> CustomerPass:
        uid = UUID(str(user.id))
        pt = await self.session.get(LessonPassType, data.pass_type_id)
        if not pt:
            raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")
        if pt.instructor_id != uid:
            raise HTTPException(status_code=403, detail="본인 수강권 상품만 발급할 수 있습니다.")
        if not pt.is_active:
            raise HTTPException(status_code=400, detail="비활성화된 수강권 상품입니다.")

        customer = await self.session.get(User, data.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
        if user.role == "INSTRUCTOR" and customer.manager_id != uid:
            raise HTTPException(status_code=403, detail="담당 고객에게만 수강권을 발급할 수 있습니다.")

        cp = CustomerPass(
            pass_type_id=pt.id,
            customer_id=data.customer_id,
            instructor_id=uid,
            pass_name=pt.name,
            duration_hours=pt.duration_hours,
            sessions_total=pt.session_count,
            sessions_used=0,
            price_paid=data.price_paid,
            status="ACTIVE",
            note=data.note,
        )
        self.session.add(cp)
        await self.session.commit()
        await self.session.refresh(cp)
        return cp

    async def get_own_customer_pass(self, customer_pass_id: int, instructor_id: UUID) -> CustomerPass:
        cp = await self.session.get(CustomerPass, customer_pass_id)
        if not cp:
            raise HTTPException(status_code=404, detail="수강권을 찾을 수 없습니다.")
        if cp.instructor_id != instructor_id:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        return cp

    # 사용 횟수는 총 횟수를 넘을 수 없고, 다 쓰면 자동 COMPLETED
    async def update_customer_pass(self, cp: CustomerPass, data: CustomerPassUpdate) -> CustomerPass:
        patch = data.model_dump(exclude_none=True)
        if patch.get("sessions_used", cp.sessions_used) > cp.sessions_total:
            raise HTTPException(status_code=400, detail="사용 횟수는 총 횟수를 넘을 수 없습니다.")
        for field, value in patch.items():
            setattr(cp, field, value)
        if cp.sessions_used >= cp.sessions_total and cp.status == "ACTIVE":
            cp.status = "COMPLETED"
        self.session.add(cp)
        await self.session.commit()
        await self.session.refresh(cp)
        return cp

    # 강사 서비스: 횟수 추가. 다 쓴(COMPLETED) 수강권은 다시 ACTIVE
    async def add_sessions(self, cp: CustomerPass, sessions: int, note: Optional[str]) -> CustomerPass:
        if sessions <= 0:
            raise HTTPException(status_code=400, detail="추가 횟수는 1 이상이어야 합니다.")
        cp.sessions_total += sessions
        if note:
            cp.note = (cp.note + "\n" + note).strip() if cp.note else note
        if cp.status == "COMPLETED":
            cp.status = "ACTIVE"
        self.session.add(cp)
        await self.session.commit()
        await self.session.refresh(cp)
        return cp

    async def deduct_for_lesson(self, customer_id: UUID, instructor_id: UUID) -> None:
        """레슨 완료·노쇼 시 그 강사의 활성 수강권에서 1회 차감 (commit 은 호출한 쪽에서)"""
        res = await self.session.execute(
            select(CustomerPass)
            .where(
                CustomerPass.customer_id == customer_id,
                CustomerPass.instructor_id == instructor_id,
                CustomerPass.status == "ACTIVE",
            )
            .limit(1)
        )
        active_pass = res.scalars().first()
        if active_pass and active_pass.sessions_used < active_pass.sessions_total:
            active_pass.sessions_used += 1
            if active_pass.sessions_used >= active_pass.sessions_total:
                active_pass.status = "COMPLETED"
            self.session.add(active_pass)

    # ── 응답 조립용 ──────────────────────────────────────────────────────────

    async def get_user(self, user_id: UUID) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_type(self, pass_type_id: int) -> Optional[LessonPassType]:
        return await self.session.get(LessonPassType, pass_type_id)

    # ── 계약 기록 보존 (회원 삭제 시) ─────────────────────────────────────────
    # 발급된 수강권은 계약 기록. 기준은 마지막 변경(사용·상태 변경) 시점

    @staticmethod
    def _of_user(user_id: UUID):
        return or_(CustomerPass.customer_id == user_id, CustomerPass.instructor_id == user_id)

    async def count_retained_for_user(self, user_id: UUID) -> int:
        """보존 기간이 끝나지 않은 발급 수강권 수"""
        return (
            await self.session.execute(
                select(func.count()).select_from(CustomerPass).where(self._of_user(user_id), CustomerPass.updated_at > retention_cutoff())
            )
        ).scalar_one()

    async def delete_expired_for_user(self, user_id: UUID) -> None:
        """보존 기간이 끝난 발급 수강권, 그리고 (강사라면) 더 이상 발급 기록이 없는 수강권 상품 삭제 (commit 은 호출한 쪽에서)"""
        await self.session.execute(
            delete(CustomerPass).where(self._of_user(user_id), CustomerPass.updated_at <= retention_cutoff())
        )
        still_issued = select(CustomerPass.pass_type_id)
        await self.session.execute(
            delete(LessonPassType).where(LessonPassType.instructor_id == user_id, LessonPassType.id.not_in(still_issued))
        )
