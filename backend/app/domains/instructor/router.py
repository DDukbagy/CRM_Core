from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, CurrentUser, get_current_user
from app.db.session import get_session
from app.domains.instructor.repository import InstructorRepository
from app.domains.instructor.schemas import (
    InstructorStaffCreate,
    InstructorStaffRead,
    InstructorPublicRead,
)
from app.domains.matching.models import NAMED_FEE

router = APIRouter(prefix="/instructors", tags=["Instructor"])


# ── Staff 관리 ───────────────────────────────────────────────

@router.post("/me/staff", status_code=status.HTTP_201_CREATED)
async def add_staff(
    payload: InstructorStaffCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    await InstructorRepository(session).add_staff(UUID(str(user.id)), payload.staff_email)
    return {"ok": True}


@router.delete("/me/staff/{staff_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    staff_user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    await InstructorRepository(session).remove_staff(UUID(str(user.id)), staff_user_id)
    return None


@router.get("/me/staff", response_model=list[InstructorStaffRead])
async def list_staff(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    rows = await InstructorRepository(session).list_staff(UUID(str(user.id)))
    return [
        InstructorStaffRead(
            staff_user_id=row.staff_user_id,
            email=row.email,
            username=row.username,
            display_name=row.display_name,
            created_at=row.created_at,
        )
        for row in rows
    ]


# ── 강사 신청/승인 ───────────────────────────────────────────

@router.post("/apply")
async def apply_instructor(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """CUSTOMER → INSTRUCTOR 신청 (상태: PENDING)"""
    u = await InstructorRepository(session).apply(UUID(str(user.id)))
    return {"ok": True, "id": str(u.id), "role": u.role, "status": u.status}


@router.get("/pending")
async def list_pending_instructors(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """ADMIN: 승인 대기 강사 목록"""
    return [
        {"id": str(u.id), "email": u.email, "username": u.username, "display_name": u.display_name, "created_at": u.created_at}
        for u in await InstructorRepository(session).list_pending()
    ]


@router.post("/{user_id}/approve")
async def approve_instructor(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """ADMIN: 강사 승인"""
    target = await InstructorRepository(session).approve(user_id)
    return {"ok": True, "id": str(target.id), "role": target.role, "status": target.status}


# ── 강사 공개 목록 ───────────────────────────────────────────

@router.get("/public", response_model=list[InstructorPublicRead])
async def list_instructors_public(
    location: str | None = None,
    specialty: str | None = None,
    name: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(get_current_user),
):
    """활성 강사 목록 (고객 앱 매칭·검색)"""
    result = []
    for u, specialties in await InstructorRepository(session).list_public(location, specialty, name):
        tier = (u.instructor_tier or "NORMAL").upper()
        result.append(
            InstructorPublicRead(
                id=u.id,
                display_name=u.display_name,
                username=u.username,
                instructor_tier=tier,
                match_fee=NAMED_FEE if tier == "NAMED" else 0,
                is_active=u.is_active,
                location=u.instructor_location,
                specialties=specialties,
                bio=u.instructor_bio,
            )
        )
    return result


# ── 전화번호로 고객 조회 + 담당 직접 등록 ────────────────────

@router.get("/customers/lookup")
async def lookup_customer_by_phone(
    phone: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """전화번호로 고객 조회 (강사 전용)"""
    customer, manager_name = await InstructorRepository(session).lookup_customer_by_phone(phone)
    return {
        "id": str(customer.id),
        "display_name": customer.display_name,
        "username": customer.username,
        "phone": customer.phone,
        "manager_id": str(customer.manager_id) if customer.manager_id else None,
        "manager_name": manager_name,
        "is_my_customer": str(customer.manager_id) == str(user.id) if customer.manager_id else False,
    }


@router.post("/customers/{customer_id}/assign", status_code=status.HTTP_200_OK)
async def assign_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """고객을 담당 고객으로 즉시 등록 (강사 전용)"""
    await InstructorRepository(session).assign_customer(customer_id, UUID(str(user.id)))
    return {"ok": True, "customer_id": str(customer_id), "manager_id": str(user.id), "message": "담당 고객으로 등록되었습니다."}


# ── 출석 / 통계 ─────────────────────────────────────────────

@router.get("/me/stats")
async def get_my_stats(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사 대시보드용 통계: 담당 고객 수, 예약 현황, 출석률"""
    return await InstructorRepository(session).my_stats(UUID(str(user.id)))


@router.get("/me/stats/customer/{customer_id}")
async def get_customer_stats(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """특정 고객의 출석 통계 (담당 강사만 조회 가능)"""
    return await InstructorRepository(session).customer_stats(UUID(str(user.id)), customer_id)
