from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.passes.models import CustomerPass
from app.domains.passes.repository import PassRepository
from app.domains.passes.schemas import (
    PassTypeCreate, PassTypeRead, PassTypeUpdate,
    CustomerPassAssign, CustomerPassRead, CustomerPassUpdate,
    InstructorBrief, AddSessionsRequest,
)

router = APIRouter(prefix="/passes", tags=["Passes"])


# ─── 권한 확인 ───────────────────────────────────────────────────────────────

def _require_instructor(user: CurrentUser) -> None:
    if user.role not in ("INSTRUCTOR", "ADMIN"):
        raise HTTPException(status_code=403, detail="강사 전용 기능입니다.")


def _require_customer(user: CurrentUser) -> None:
    if user.role not in ("CUSTOMER", "ADMIN"):
        raise HTTPException(status_code=403, detail="고객 전용 기능입니다.")


# ─── 응답 변환 ───────────────────────────────────────────────────────────────

async def _to_read(
    repo: PassRepository,
    cp: CustomerPass,
    *,
    include_customer_name: bool = False,
    include_instructor: bool = False,
    include_pass_type: bool = False,
) -> CustomerPassRead:
    read = CustomerPassRead.model_validate(cp)
    read.sessions_remaining = cp.sessions_total - cp.sessions_used
    if include_customer_name:
        customer = await repo.get_user(cp.customer_id)
        read.customer_name = customer.display_name if customer else str(cp.customer_id)
    if include_instructor:
        instructor = await repo.get_user(cp.instructor_id)
        if instructor:
            read.instructor = InstructorBrief.model_validate(instructor)
    if include_pass_type:
        pt = await repo.get_type(cp.pass_type_id)
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
    types = await PassRepository(session).list_types_of(UUID(str(current_user.id)))
    return [PassTypeRead.model_validate(pt) for pt in types]


@router.post("/types", response_model=PassTypeRead, status_code=status.HTTP_201_CREATED)
async def create_pass_type(
    data: PassTypeCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수강권 상품 생성 (강사 전용)"""
    _require_instructor(current_user)
    pt = await PassRepository(session).create_type(data, UUID(str(current_user.id)))
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
    repo = PassRepository(session)
    pt = await repo.get_own_type(pass_type_id, UUID(str(current_user.id)))
    return PassTypeRead.model_validate(await repo.update_type(pt, data))


@router.delete("/types/{pass_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pass_type(
    pass_type_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수강권 상품 삭제 (강사 전용). 활성 고객 수강권이 있으면 409 → 비활성화(is_active=false) 권장"""
    _require_instructor(current_user)
    repo = PassRepository(session)
    pt = await repo.get_own_type(pass_type_id, UUID(str(current_user.id)))
    await repo.delete_type(pt)


# ─── 강사: 고객 수강권 발급 및 관리 ────────────────────────────────────────────

@router.get("/customer-passes", response_model=list[CustomerPassRead])
async def list_my_customer_passes(
    customer_id: Optional[UUID] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 고객들의 수강권 목록 (강사 전용). customer_id 를 주면 그 고객 것만 (고객 상세 화면)"""
    _require_instructor(current_user)
    repo = PassRepository(session)
    passes = await repo.list_by_instructor(UUID(str(current_user.id)))
    if customer_id is not None:
        passes = [cp for cp in passes if cp.customer_id == customer_id]
    return [await _to_read(repo, cp, include_customer_name=True) for cp in passes]


@router.post("/assign", response_model=CustomerPassRead, status_code=status.HTTP_201_CREATED)
async def assign_pass(
    data: CustomerPassAssign,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """고객에게 수강권 발급 (강사 전용)"""
    _require_instructor(current_user)
    repo = PassRepository(session)
    cp = await repo.assign(data, current_user)
    return await _to_read(repo, cp, include_customer_name=True)


@router.patch("/customer-passes/{customer_pass_id}", response_model=CustomerPassRead)
async def update_customer_pass(
    customer_pass_id: int,
    data: CustomerPassUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """수강권 업데이트 (강사 전용). 사용 횟수가 총 횟수에 도달하면 자동 COMPLETED"""
    _require_instructor(current_user)
    repo = PassRepository(session)
    cp = await repo.get_own_customer_pass(customer_pass_id, UUID(str(current_user.id)))
    cp = await repo.update_customer_pass(cp, data)
    return await _to_read(repo, cp, include_customer_name=True)


@router.post("/customer-passes/{customer_pass_id}/add-sessions", response_model=CustomerPassRead)
async def add_sessions_service(
    customer_pass_id: int,
    data: AddSessionsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """강사 서비스: 기존 수강권에 횟수 추가 (sessions_total 증가)"""
    _require_instructor(current_user)
    repo = PassRepository(session)
    cp = await repo.get_own_customer_pass(customer_pass_id, UUID(str(current_user.id)))
    cp = await repo.add_sessions(cp, data.sessions, data.note)
    return await _to_read(repo, cp, include_customer_name=True)


# ─── 고객: 내 수강권 조회 ─────────────────────────────────────────────────────

@router.get("/me", response_model=list[CustomerPassRead])
async def get_my_passes(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """내 수강권 목록 (고객 전용)"""
    _require_customer(current_user)
    repo = PassRepository(session)
    passes = await repo.list_by_customer(UUID(str(current_user.id)))
    return [await _to_read(repo, cp, include_instructor=True, include_pass_type=True) for cp in passes]


# ─── 공개: 강사 수강권 상품 목록 ─────────────────────────────────────────────

@router.get("/instructor/{instructor_id}/types", response_model=list[PassTypeRead])
async def get_instructor_pass_types(
    instructor_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """특정 강사의 활성 수강권 상품 목록 (고객 → 강사 프로필 조회용)"""
    types = await PassRepository(session).list_types_of(instructor_id, active_only=True)
    return [PassTypeRead.model_validate(pt) for pt in types]
