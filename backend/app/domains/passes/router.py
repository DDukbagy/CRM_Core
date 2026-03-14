from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.passes.models import LessonPassType, CustomerPass
from app.domains.passes.schemas import (
    PassTypeCreate, PassTypeRead, PassTypeUpdate,
    CustomerPassAssign, CustomerPassRead, CustomerPassUpdate,
    InstructorBrief, AddSessionsRequest,
)
from app.domains.users.models import User

router = APIRouter(prefix="/passes", tags=["Passes"])


# ─── helpers ─────────────────────────────────────────────────────────────────

def _require_instructor(user: CurrentUser) -> None:
    if user.role not in ("INSTRUCTOR", "ADMIN"):
        raise HTTPException(status_code=403, detail="강사 전용 기능입니다.")


def _require_customer(user: CurrentUser) -> None:
    if user.role not in ("CUSTOMER", "ADMIN"):
        raise HTTPException(status_code=403, detail="고객 전용 기능입니다.")


async def _enrich_customer_pass(
    cp: CustomerPass,
    session: AsyncSession,
    include_instructor: bool = False,
    include_pass_type: bool = False,
) -> CustomerPassRead:
    read = CustomerPassRead.model_validate(cp)
    read.sessions_remaining = cp.sessions_total - cp.sessions_used

    if include_instructor:
        instructor = await session.get(User, cp.instructor_id)
        if instructor:
            read.instructor = InstructorBrief.model_validate(instructor)

    if include_pass_type:
        pt = await session.get(LessonPassType, cp.pass_type_id)
        if pt:
            read.pass_type = PassTypeRead.model_validate(pt)

    return read


# ─── 강사: 수강권 상품 CRUD ────────────────────────────────────────────────────

@router.get("/types", response_model=list[PassTypeRead])
async def list_my_pass_types(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 수강권 상품 목록 (강사 전용)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))
    result = await session.execute(
        select(LessonPassType)
        .where(LessonPassType.instructor_id == uid)
        .order_by(LessonPassType.duration_hours, LessonPassType.id)
    )
    return [PassTypeRead.model_validate(pt) for pt in result.scalars().all()]


@router.post("/types", response_model=PassTypeRead, status_code=status.HTTP_201_CREATED)
async def create_pass_type(
    data: PassTypeCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수강권 상품 생성 (강사 전용)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))
    pt = LessonPassType(
        instructor_id=uid,
        name=data.name,
        duration_hours=data.duration_hours,
        session_count=data.session_count,
        price=data.price,
        description=data.description,
    )
    session.add(pt)
    await session.commit()
    await session.refresh(pt)
    return PassTypeRead.model_validate(pt)


@router.patch("/types/{pass_type_id}", response_model=PassTypeRead)
async def update_pass_type(
    pass_type_id: int,
    data: PassTypeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수강권 상품 수정 (강사 전용)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))
    pt = await session.get(LessonPassType, pass_type_id)
    if not pt:
        raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")
    if pt.instructor_id != uid:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(pt, field, value)
    session.add(pt)
    await session.commit()
    await session.refresh(pt)
    return PassTypeRead.model_validate(pt)


@router.delete("/types/{pass_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pass_type(
    pass_type_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    수강권 상품 삭제 (강사 전용)
    - 활성 고객 수강권이 존재하면 409 반환 → 비활성화(is_active=false) 권장
    """
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))
    pt = await session.get(LessonPassType, pass_type_id)
    if not pt:
        raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")
    if pt.instructor_id != uid:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    active_result = await session.execute(
        select(CustomerPass).where(
            CustomerPass.pass_type_id == pass_type_id,
            CustomerPass.status == "ACTIVE",
        ).limit(1)
    )
    if active_result.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="활성 수강권이 있어 삭제할 수 없습니다. 비활성화를 사용하세요.",
        )

    await session.delete(pt)
    await session.commit()


# ─── 강사: 고객 수강권 발급 및 관리 ────────────────────────────────────────────

@router.get("/customer-passes", response_model=list[CustomerPassRead])
async def list_my_customer_passes(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 고객들의 수강권 목록 (강사 전용)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))
    result = await session.execute(
        select(CustomerPass)
        .where(CustomerPass.instructor_id == uid)
        .order_by(CustomerPass.status, CustomerPass.created_at.desc())
    )
    passes = result.scalars().all()
    out = []
    for cp in passes:
        customer = await session.get(User, cp.customer_id)
        read = await _enrich_customer_pass(cp, session)
        read.customer_name = customer.display_name if customer else str(cp.customer_id)
        out.append(read)
    return out


@router.post("/assign", response_model=CustomerPassRead, status_code=status.HTTP_201_CREATED)
async def assign_pass(
    data: CustomerPassAssign,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """고객에게 수강권 발급 (강사 전용)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))

    pt = await session.get(LessonPassType, data.pass_type_id)
    if not pt:
        raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")
    if pt.instructor_id != uid:
        raise HTTPException(status_code=403, detail="본인 수강권 상품만 발급할 수 있습니다.")
    if not pt.is_active:
        raise HTTPException(status_code=400, detail="비활성화된 수강권 상품입니다.")

    customer = await session.get(User, data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")

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
    session.add(cp)
    await session.commit()
    await session.refresh(cp)

    read = await _enrich_customer_pass(cp, session)
    read.customer_name = customer.display_name
    return read


@router.patch("/customer-passes/{customer_pass_id}", response_model=CustomerPassRead)
async def update_customer_pass(
    customer_pass_id: int,
    data: CustomerPassUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    수강권 업데이트 (강사 전용)
    - sessions_used 증가 시 sessions_total 도달하면 자동 COMPLETED 처리
    """
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))

    cp = await session.get(CustomerPass, customer_pass_id)
    if not cp:
        raise HTTPException(status_code=404, detail="수강권을 찾을 수 없습니다.")
    if cp.instructor_id != uid:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cp, field, value)

    # 모든 회차 사용 완료 시 자동 완료 처리
    if cp.sessions_used >= cp.sessions_total and cp.status == "ACTIVE":
        cp.status = "COMPLETED"

    session.add(cp)
    await session.commit()
    await session.refresh(cp)

    customer = await session.get(User, cp.customer_id)
    read = await _enrich_customer_pass(cp, session)
    read.customer_name = customer.display_name if customer else str(cp.customer_id)
    return read


@router.post("/customer-passes/{customer_pass_id}/add-sessions", response_model=CustomerPassRead)
async def add_sessions_service(
    customer_pass_id: int,
    data: AddSessionsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """강사 서비스: 기존 수강권에 횟수 추가 (sessions_total 증가)"""
    _require_instructor(current_user)
    uid = UUID(str(current_user.id))

    cp = await session.get(CustomerPass, customer_pass_id)
    if not cp:
        raise HTTPException(status_code=404, detail="수강권을 찾을 수 없습니다.")
    if cp.instructor_id != uid:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    if data.sessions <= 0:
        raise HTTPException(status_code=400, detail="추가 횟수는 1 이상이어야 합니다.")

    cp.sessions_total += data.sessions
    if data.note:
        cp.note = ((cp.note + "\n" + data.note).strip() if cp.note else data.note)
    # COMPLETED 상태였다면 다시 ACTIVE로 전환
    if cp.status == "COMPLETED":
        cp.status = "ACTIVE"

    session.add(cp)
    await session.commit()
    await session.refresh(cp)

    customer = await session.get(User, cp.customer_id)
    read = await _enrich_customer_pass(cp, session)
    read.customer_name = customer.display_name if customer else str(cp.customer_id)
    return read


# ─── 고객: 내 수강권 조회 ─────────────────────────────────────────────────────

@router.get("/me", response_model=list[CustomerPassRead])
async def get_my_passes(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 수강권 목록 (고객 전용)"""
    _require_customer(current_user)
    uid = UUID(str(current_user.id))
    result = await session.execute(
        select(CustomerPass)
        .where(CustomerPass.customer_id == uid)
        .order_by(CustomerPass.status, CustomerPass.created_at.desc())
    )
    out = []
    for cp in result.scalars().all():
        read = await _enrich_customer_pass(cp, session, include_instructor=True, include_pass_type=True)
        out.append(read)
    return out


# ─── 공개: 강사 수강권 상품 목록 ─────────────────────────────────────────────

@router.get("/instructor/{instructor_id}/types", response_model=list[PassTypeRead])
async def get_instructor_pass_types(
    instructor_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """특정 강사의 활성 수강권 상품 목록 (고객 → 강사 프로필 조회용)"""
    result = await session.execute(
        select(LessonPassType)
        .where(
            LessonPassType.instructor_id == instructor_id,
            LessonPassType.is_active == True,
        )
        .order_by(LessonPassType.duration_hours, LessonPassType.session_count)
    )
    return [PassTypeRead.model_validate(pt) for pt in result.scalars().all()]
