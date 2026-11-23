# 수강권 저장소: 상품 관리, 발급·사용·횟수 추가, 기록 보존
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, delete, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser
from app.core.logging import log_event
from app.core.retention import retention_cutoff
from app.domains.booking.models import ACTIVE_LESSON_STATUSES, Booking
from app.domains.passes.models import CustomerPass, LessonPassType
from app.domains.passes.schemas import CustomerPassAssign, CustomerPassUpdate, PassTypeCreate, PassTypeUpdate
from app.domains.users.models import User


class PassRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 수강권 상품 (강사)

    # 강사의 수강권 상품 목록
    async def list_types_of(self, instructor_id: UUID, active_only: bool = False) -> list[LessonPassType]:
        stmt = select(LessonPassType).where(LessonPassType.instructor_id == instructor_id)
        if active_only:
            stmt = stmt.where(LessonPassType.is_active == True).order_by(  # noqa: E712
                LessonPassType.duration_hours, LessonPassType.session_count
            )
        else:
            stmt = stmt.order_by(LessonPassType.duration_hours, LessonPassType.id)
        return list((await self.session.execute(stmt)).scalars().all())

    # 수강권 상품 만들기
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

    # 수강권 상품 수정
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

    # 고객 수강권

    # 강사가 발급한 수강권 목록
    async def list_by_instructor(self, instructor_id: UUID) -> list[CustomerPass]:
        res = await self.session.execute(
            select(CustomerPass)
            .where(CustomerPass.instructor_id == instructor_id)
            .order_by(CustomerPass.status, CustomerPass.created_at.desc())
        )
        return list(res.scalars().all())

    # 고객의 수강권 목록
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
        log_event("pass.assigned", customer_pass_id=cp.id, actor_id=str(user.id), customer_id=str(cp.customer_id),
                  sessions_total=cp.sessions_total)
        return cp

    async def get_own_customer_pass(self, customer_pass_id: int, instructor_id: UUID) -> CustomerPass:
        cp = await self.session.get(CustomerPass, customer_pass_id)
        if not cp:
            raise HTTPException(status_code=404, detail="수강권을 찾을 수 없습니다.")
        if cp.instructor_id != instructor_id:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        return cp

    # 사용 횟수는 총 횟수를 넘을 수 없고, 다 쓰면 자동 COMPLETED
    async def _lock(self, cp: CustomerPass) -> CustomerPass:
        """수강권 행을 잠그고 지금 값으로 다시 읽는다 (잠금은 commit 까지)

        강사의 수정은 "읽고 → 계산 → 저장"이라, 읽은 뒤 저장하기 전에 완료의 차감이나 다른 수정이 끼어들면
        옛 값으로 계산한 결과를 덮어쓴다. 저장 직전에 잠그고 다시 읽으면 겹친 요청들이 차례로 처리된다.
        차감(deduct_for_lesson)과 예약 신청(lock_passes_for_booking)도 같은 행을 잠그거나 조건부로 고치므로 서로 기다린다.
        """
        return (await self.session.execute(
            select(CustomerPass).where(CustomerPass.id == cp.id).with_for_update().execution_options(populate_existing=True)
        )).scalar_one()

    async def _reserved(self, cp: CustomerPass) -> int:
        """이 수강권에 걸려 있는 진행 중 예약 수 (신청·확정·취소 신청). 이 예약들은 완료될 때 이 수강권에서 차감된다"""
        return (await self.session.execute(
            select(func.count()).select_from(Booking).where(
                Booking.customer_pass_id == cp.id, Booking.status.in_(ACTIVE_LESSON_STATUSES)
            )
        )).scalar_one()

    async def update_customer_pass(self, cp: CustomerPass, data: CustomerPassUpdate) -> CustomerPass:
        """수동 수정 (사용 횟수·상태·메모). 걸려 있는 예약을 완료할 수 없게 만드는 수정은 409 로 거부한다

        - 진행 중이 아닌 상태(취소·만료·다 씀)로 바꾸기: 걸린 예약이 있으면 거부 (예약을 먼저 처리해야 한다)
        - 사용 횟수 올리기: 남은 횟수가 걸린 예약 수보다 적어지면 거부
        """
        cp = await self._lock(cp)
        patch = data.model_dump(exclude_none=True)
        new_used = patch.get("sessions_used", cp.sessions_used)
        new_status = patch.get("status", cp.status)
        if new_used > cp.sessions_total:
            raise HTTPException(status_code=400, detail="사용 횟수는 총 횟수를 넘을 수 없습니다.")

        closing = new_status != "ACTIVE" and cp.status == "ACTIVE"
        raising = new_used > cp.sessions_used
        if closing or raising:
            reserved = await self._reserved(cp)
            if reserved and closing:
                raise HTTPException(
                    status_code=409,
                    detail=f"진행 중인 예약이 {reserved}건 있어 수강권 상태를 바꿀 수 없습니다. 예약을 먼저 처리해 주세요.",
                )
            if reserved and cp.sessions_total - new_used < reserved:
                raise HTTPException(
                    status_code=409,
                    detail=f"진행 중인 예약이 {reserved}건 있어 남은 횟수를 {reserved}회 아래로 줄일 수 없습니다. 예약을 먼저 처리해 주세요.",
                )

        for field, value in patch.items():
            setattr(cp, field, value)
        if cp.sessions_used >= cp.sessions_total and cp.status == "ACTIVE":
            cp.status = "COMPLETED"
        self.session.add(cp)
        await self.session.commit()
        await self.session.refresh(cp)
        # 본인 수강권만 수정할 수 있으므로(get_own_customer_pass) 처리한 사람 = 발급한 강사. 메모 내용은 남기지 않는다
        log_event("pass.updated", customer_pass_id=cp.id, actor_id=str(cp.instructor_id), fields=sorted(patch),
                  sessions_used=cp.sessions_used, sessions_total=cp.sessions_total, status=cp.status)
        return cp

    # 강사 서비스: 횟수 추가. 다 쓴(COMPLETED) 수강권은 다시 ACTIVE
    async def add_sessions(self, cp: CustomerPass, sessions: int, note: Optional[str]) -> CustomerPass:
        if sessions <= 0:
            raise HTTPException(status_code=400, detail="추가 횟수는 1 이상이어야 합니다.")
        cp = await self._lock(cp)  # 지금 값에 더한다 (동시에 온 추가·차감이 사라지지 않게)
        cp.sessions_total += sessions
        if note:
            cp.note = (cp.note + "\n" + note).strip() if cp.note else note
        if cp.status == "COMPLETED":
            cp.status = "ACTIVE"
        self.session.add(cp)
        await self.session.commit()
        await self.session.refresh(cp)
        log_event("pass.sessions_added", customer_pass_id=cp.id, actor_id=str(cp.instructor_id), added=sessions,
                  sessions_used=cp.sessions_used, sessions_total=cp.sessions_total)
        return cp

    async def lock_passes_for_booking(
        self, customer_id: UUID, instructor_id: UUID, customer_pass_id: Optional[int]
    ) -> list[CustomerPass]:
        """예약에 쓸 후보 수강권을 잠그고 돌려준다 (먼저 발급된 순, commit 은 호출한 쪽에서)

        - customer_pass_id 를 주면 그 하나만. 그 고객의 그 강사 수강권이 아니면(없는 번호 포함) 400.
          없는 번호와 남의 번호를 같은 응답으로 묶어, 남의 수강권 번호가 있는지 드러나지 않게 한다
        - 안 주면 그 고객의 그 강사 활성 수강권 전부
        행을 잠그므로(SELECT ... FOR UPDATE) 같은 수강권으로 동시에 예약해도 한 번에 하나씩 잔여를 센다.
        """
        stmt = (
            select(CustomerPass)
            .where(CustomerPass.customer_id == customer_id, CustomerPass.instructor_id == instructor_id)
            .order_by(CustomerPass.id)
            .with_for_update()
        )
        if customer_pass_id is not None:
            cp = (await self.session.execute(stmt.where(CustomerPass.id == customer_pass_id))).scalars().first()
            if cp is None:
                raise HTTPException(status_code=400, detail="쓸 수 없는 수강권입니다.")
            return [cp]
        return list((await self.session.execute(stmt.where(CustomerPass.status == "ACTIVE"))).scalars().all())

    async def deduct_for_lesson(self, customer_pass_id: int, customer_id: UUID, instructor_id: UUID) -> int:
        """레슨 완료·노쇼 시 예약에 고정된 수강권에서 1회 차감하고 그 수강권 id 를 돌려준다 (commit 은 호출한 쪽에서)

        조건부 UPDATE 한 문장으로 "잔여가 있으면 +1" 을 한다. Python 에서 읽고 더해 저장하면
        동시에 온 요청이 같은 값을 읽어 차감 1회가 사라진다 (갱신 손실).
        나중 요청의 UPDATE 는 앞 트랜잭션의 커밋을 기다린 뒤 WHERE 를 다시 확인하므로 잔여를 넘겨 차감하지 않는다.
        고정된 수강권을 다 썼거나 활성이 아니면 409 — 호출한 쪽의 예약 상태 변경도 커밋되지 않는다.
        고객·강사 조건은 예약할 때 이미 확인했지만, 다른 사람의 수강권에서 차감되는 일이 없도록 한 번 더 건다.
        """
        res = await self.session.execute(
            update(CustomerPass)
            .where(
                CustomerPass.id == customer_pass_id,
                CustomerPass.customer_id == customer_id,
                CustomerPass.instructor_id == instructor_id,
                CustomerPass.status == "ACTIVE",
                CustomerPass.sessions_used < CustomerPass.sessions_total,
            )
            .values(
                sessions_used=CustomerPass.sessions_used + 1,
                # SET 의 오른쪽은 바뀌기 전 값으로 계산된다: 이번 차감으로 다 쓰면 COMPLETED
                status=case(
                    (CustomerPass.sessions_used + 1 >= CustomerPass.sessions_total, "COMPLETED"),
                    else_=CustomerPass.status,
                ),
            )
            .returning(CustomerPass.id)
            .execution_options(synchronize_session=False)
        )
        row = res.first()
        if row is None:
            raise HTTPException(status_code=409, detail="사용할 수 있는 수강권이 없습니다.")
        return row[0]

    # 응답 조립용

    async def get_user(self, user_id: UUID) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_type(self, pass_type_id: int) -> Optional[LessonPassType]:
        return await self.session.get(LessonPassType, pass_type_id)

    # 계약 기록 보존 (회원 삭제 시)
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

    async def ensure_linkable_to_payment(self, customer_pass_id: int, customer_id: UUID, instructor_id: Optional[UUID]) -> None:
        """결제에 연결할 수강권 확인: 그 고객의 수강권이어야 하고, 강사는 자기가 발급한 것만"""
        cp = await self.session.get(CustomerPass, customer_pass_id)
        if not cp:
            raise HTTPException(status_code=404, detail="수강권을 찾을 수 없습니다.")
        if cp.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="수강권과 고객 정보가 일치하지 않습니다.")
        if instructor_id is not None and cp.instructor_id != instructor_id:
            raise HTTPException(status_code=403, detail="본인이 발급한 수강권만 결제에 연결할 수 있습니다.")

