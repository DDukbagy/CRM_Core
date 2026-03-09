from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.domains.calendar.models import Booking
from app.domains.instructor.models import MatchRequest
from app.domains.instructor.schemas import (
    InstructorStaffCreate,
    InstructorStaffRead,
    InstructorPublicRead,
    MatchRequestCreate,
    MatchRequestRead,
)
from app.domains.users.models import User

router = APIRouter(prefix="/instructors", tags=["Instructor"])

NAMED_FEE = 5_000  # 네임드 강사 매칭 수수료(원)


# ── Staff 관리 ───────────────────────────────────────────────

@router.post("/me/staff", status_code=status.HTTP_201_CREATED)
async def add_staff(
    payload: InstructorStaffCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))

    # 이메일로 스태프 유저 조회 (ORM)
    res = await session.execute(select(User).where(User.email == payload.staff_email))
    staff_user = res.scalar_one_or_none()
    if not staff_user:
        raise HTTPException(status_code=404, detail="Staff user not found")

    if staff_user.id == instructor_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as staff")

    try:
        await session.execute(
            text(
                "INSERT INTO public.instructor_staff (instructor_id, staff_user_id) "
                "VALUES (:instructor_id, :staff_user_id)"
            ),
            {"instructor_id": str(instructor_id), "staff_user_id": str(staff_user.id)},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Staff already assigned")

    return {"ok": True}


@router.delete("/me/staff/{staff_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    staff_user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))
    res = await session.execute(
        text(
            "DELETE FROM public.instructor_staff "
            "WHERE instructor_id = :instructor_id AND staff_user_id = :staff_user_id"
        ),
        {"instructor_id": str(instructor_id), "staff_user_id": str(staff_user_id)},
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Staff relation not found")
    await session.commit()
    return None


@router.get("/me/staff", response_model=list[InstructorStaffRead])
async def list_staff(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))
    res = await session.execute(
        text(
            """
            SELECT u.id AS staff_user_id, u.email, u.username, u.display_name, s.created_at
            FROM public.instructor_staff s
            JOIN public.users u ON u.id = s.staff_user_id
            WHERE s.instructor_id = :instructor_id
            ORDER BY s.created_at DESC
            """
        ),
        {"instructor_id": str(instructor_id)},
    )
    return [
        InstructorStaffRead(
            staff_user_id=row.staff_user_id,
            email=row.email,
            username=row.username,
            display_name=row.display_name,
            created_at=row.created_at,
        )
        for row in res
    ]


# ── 강사 신청/승인 ───────────────────────────────────────────

@router.post("/apply")
async def apply_instructor(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """CUSTOMER → INSTRUCTOR 신청 (상태: PENDING)"""
    res = await session.execute(select(User).where(User.id == UUID(str(user.id))))
    db_user = res.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_role = (db_user.role or "").upper()
    if current_role == "INSTRUCTOR":
        return {"ok": True, "role": current_role, "status": db_user.status}
    if current_role != "CUSTOMER":
        raise HTTPException(status_code=400, detail="Invalid role transition")

    db_user.role = "INSTRUCTOR"
    db_user.status = "PENDING"
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return {"ok": True, "id": str(db_user.id), "role": db_user.role, "status": db_user.status}


@router.get("/pending")
async def list_pending_instructors(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """ADMIN: 승인 대기 강사 목록"""
    res = await session.execute(
        select(User)
        .where(
            and_(
                User.role == "INSTRUCTOR",
                User.status == "PENDING",
                User.is_active == True,
            )
        )
        .order_by(User.created_at.asc())
    )
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "display_name": u.display_name,
            "created_at": u.created_at,
        }
        for u in res.scalars().all()
    ]


@router.post("/{user_id}/approve")
async def approve_instructor(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """ADMIN: 강사 승인"""
    if settings.SUPER_ADMIN_USER_ID and str(user_id) == str(settings.SUPER_ADMIN_USER_ID):
        raise HTTPException(status_code=403, detail="Cannot modify super admin")

    res = await session.execute(
        select(User).where(and_(User.id == user_id, User.role == "INSTRUCTOR"))
    )
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Pending instructor not found")

    target.status = "ACTIVE"
    session.add(target)
    await session.commit()
    await session.refresh(target)
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
    """활성 강사 목록 (고객 앱 매칭·검색)
    location/name 은 DB에서 필터링, specialty는 콤마 문자열이라 Python에서 처리.
    """
    conditions = [
        User.role == "INSTRUCTOR",
        User.status == "ACTIVE",
        User.is_active == True,
    ]
    if location:
        conditions.append(User.instructor_location == location)
    if name:
        conditions.append(User.display_name.ilike(f"%{name}%"))

    res = await session.execute(
        select(User)
        .where(and_(*conditions))
        .order_by(
            # NAMED 우선
            (User.instructor_tier != "NAMED").asc(),
            User.display_name.asc(),
        )
    )
    instructors = res.scalars().all()

    result = []
    for u in instructors:
        tier = (u.instructor_tier or "NORMAL").upper()
        specialties = [s.strip() for s in (u.instructor_specialties or "").split(",") if s.strip()]

        # specialty 필터 (콤마 구분 문자열이라 Python에서 처리)
        if specialty and specialty not in specialties:
            continue

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


# ── 매칭 요청 ────────────────────────────────────────────────

@router.post("/match", status_code=status.HTTP_201_CREATED, response_model=MatchRequestRead)
async def request_match(
    payload: MatchRequestCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """고객 → 강사 매칭 신청"""
    customer_id = UUID(str(user.id))
    instructor_id = payload.instructor_id

    # 강사 존재 여부 + 등급 확인 (ORM)
    instr_res = await session.execute(
        select(User).where(
            and_(
                User.id == instructor_id,
                User.role == "INSTRUCTOR",
                User.status == "ACTIVE",
                User.is_active == True,
            )
        )
    )
    instr = instr_res.scalar_one_or_none()
    if not instr:
        raise HTTPException(status_code=404, detail="강사를 찾을 수 없습니다.")

    tier = (instr.instructor_tier or "NORMAL").upper()
    fee = NAMED_FEE if tier == "NAMED" else 0

    # request_type 유효성 검사
    req_type = (payload.request_type or "MATCH").upper()
    if req_type not in ("MATCH", "CONSULTATION"):
        raise HTTPException(status_code=400, detail="request_type은 MATCH 또는 CONSULTATION 이어야 합니다.")

    # 상담 신청은 무료
    if req_type == "CONSULTATION":
        fee = 0

    # 이미 PENDING/ACCEPTED 요청 중복 방지 (request_type 단위)
    dup_res = await session.execute(
        select(MatchRequest).where(
            and_(
                MatchRequest.customer_id == customer_id,
                MatchRequest.request_type == req_type,
                MatchRequest.status.in_(["PENDING", "ACCEPTED"]),
            )
        )
    )
    if dup_res.scalar_one_or_none():
        label = "매칭" if req_type == "MATCH" else "상담"
        raise HTTPException(
            status_code=409,
            detail=f"이미 진행 중인 {label} 요청이 있습니다. 기존 요청을 취소 후 다시 신청해 주세요.",
        )

    mr = MatchRequest(
        customer_id=customer_id,
        instructor_id=instructor_id,
        request_type=req_type,
        status="PENDING",
        fee=fee,
        note=payload.note,
    )
    session.add(mr)
    await session.commit()
    await session.refresh(mr)

    return MatchRequestRead(
        id=mr.id,
        customer_id=mr.customer_id,
        instructor_id=mr.instructor_id,
        request_type=mr.request_type,
        status=mr.status,
        fee=mr.fee,
        note=mr.note,
        instructor_name=instr.display_name,
        created_at=mr.created_at,
        updated_at=mr.updated_at,
    )


@router.get("/match/me", response_model=list[MatchRequestRead])
async def get_my_match_requests(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객: 내 매칭 요청 목록 / 강사: 받은 매칭 요청 목록"""
    uid = str(user.id)
    if user.role == "CUSTOMER":
        res = await session.execute(
            text(
                """
                SELECT mr.*, u.display_name AS instructor_name
                FROM instructor_match_requests mr
                JOIN public.users u ON u.id = mr.instructor_id
                WHERE mr.customer_id = :uid
                ORDER BY mr.created_at DESC
                """
            ),
            {"uid": uid},
        )
    elif user.role in ("INSTRUCTOR", "ADMIN"):
        res = await session.execute(
            text(
                """
                SELECT mr.*, u.display_name AS customer_name
                FROM instructor_match_requests mr
                JOIN public.users u ON u.id = mr.customer_id
                WHERE mr.instructor_id = :uid
                ORDER BY mr.created_at DESC
                """
            ),
            {"uid": uid},
        )
    else:
        return []

    return [
        MatchRequestRead(
            id=r.id,
            customer_id=r.customer_id,
            instructor_id=r.instructor_id,
            request_type=getattr(r, "request_type", "MATCH"),
            status=r.status,
            fee=r.fee,
            note=r.note,
            instructor_name=getattr(r, "instructor_name", None),
            customer_name=getattr(r, "customer_name", None),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in res.fetchall()
    ]


@router.patch("/match/{request_id}/accept", response_model=MatchRequestRead)
async def accept_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 매칭 요청 수락 → customer.manager_id 설정"""
    mr = await session.get(MatchRequest, request_id)
    if not mr or str(mr.instructor_id) != str(user.id):
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if mr.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"수락할 수 없는 상태입니다: {mr.status}")

    mr.status = "ACCEPTED"
    session.add(mr)

    cust_res = await session.execute(select(User).where(User.id == mr.customer_id))
    customer = cust_res.scalar_one_or_none()

    # MATCH 타입만 manager_id 설정 (CONSULTATION은 담당 강사 연결 없음)
    if customer and getattr(mr, "request_type", "MATCH") == "MATCH":
        customer.manager_id = mr.instructor_id
        session.add(customer)

    await session.commit()
    await session.refresh(mr)

    return MatchRequestRead(
        id=mr.id,
        customer_id=mr.customer_id,
        instructor_id=mr.instructor_id,
        request_type=getattr(mr, "request_type", "MATCH"),
        status=mr.status,
        fee=mr.fee,
        note=mr.note,
        customer_name=customer.display_name if customer else None,
        created_at=mr.created_at,
        updated_at=mr.updated_at,
    )


@router.patch("/match/{request_id}/reject", response_model=MatchRequestRead)
async def reject_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 매칭 요청 거절"""
    mr = await session.get(MatchRequest, request_id)
    if not mr or str(mr.instructor_id) != str(user.id):
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if mr.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"거절할 수 없는 상태입니다: {mr.status}")

    mr.status = "REJECTED"
    session.add(mr)
    await session.commit()
    await session.refresh(mr)

    return MatchRequestRead(
        id=mr.id,
        customer_id=mr.customer_id,
        instructor_id=mr.instructor_id,
        request_type=getattr(mr, "request_type", "MATCH"),
        status=mr.status,
        fee=mr.fee,
        note=mr.note,
        created_at=mr.created_at,
        updated_at=mr.updated_at,
    )


@router.delete("/match/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """고객이 매칭 요청 취소"""
    mr = await session.get(MatchRequest, request_id)
    if not mr or str(mr.customer_id) != str(user.id):
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if mr.status not in ("PENDING",):
        raise HTTPException(status_code=400, detail="취소할 수 없는 상태입니다.")

    mr.status = "CANCELLED"
    session.add(mr)
    await session.commit()
    return None


# ── 전화번호로 고객 조회 + 담당 직접 등록 ────────────────────

@router.get("/customers/lookup")
async def lookup_customer_by_phone(
    phone: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """전화번호로 고객 조회 (강사 전용)"""
    res = await session.execute(
        select(User).where(
            and_(
                User.phone == phone,
                User.role == "CUSTOMER",
                User.is_active == True,
            )
        )
    )
    customer = res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="해당 전화번호로 등록된 고객을 찾을 수 없습니다.")

    manager_name: str | None = None
    if customer.manager_id:
        mgr_res = await session.execute(select(User.display_name).where(User.id == customer.manager_id))
        manager_name = mgr_res.scalar_one_or_none()

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
    res = await session.execute(
        select(User).where(and_(User.id == customer_id, User.is_active == True))
    )
    customer = res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    if customer.role != "CUSTOMER":
        raise HTTPException(status_code=400, detail="고객 계정만 담당 등록할 수 있습니다.")

    if customer.manager_id and str(customer.manager_id) != str(user.id):
        raise HTTPException(
            status_code=409,
            detail="이미 다른 강사의 담당 고객입니다. 고객 동의 후 변경할 수 있습니다.",
        )

    customer.manager_id = UUID(str(user.id))
    session.add(customer)
    await session.commit()

    return {
        "ok": True,
        "customer_id": str(customer_id),
        "manager_id": str(user.id),
        "message": "담당 고객으로 등록되었습니다.",
    }


# ── 출석 / 통계 ─────────────────────────────────────────────

@router.get("/me/stats")
async def get_my_stats(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사 대시보드용 통계: 담당 고객 수, 예약 현황, 출석률"""
    instructor_id = UUID(str(user.id))

    # 담당 고객 수
    cust_res = await session.execute(
        select(User).where(
            and_(User.manager_id == instructor_id, User.is_active == True)
        )
    )
    customer_count = len(cust_res.scalars().all())

    # 전체 예약 상태별 집계
    booking_res = await session.execute(
        select(Booking.status, text("count(*) AS cnt"))
        .join(User, Booking.guest_id == User.id)
        .where(User.manager_id == instructor_id)
        .group_by(Booking.status)
    )
    booking_counts: dict[str, int] = {}
    for row in booking_res:
        booking_counts[row.status] = row.cnt

    total_bookings = sum(booking_counts.values())
    completed = booking_counts.get("COMPLETED", 0)
    no_show   = booking_counts.get("NO_SHOW", 0)
    confirmed = booking_counts.get("CONFIRMED", 0)
    requested = booking_counts.get("REQUESTED", 0)
    cancelled = booking_counts.get("CANCELLED", 0)

    attended_base = completed + no_show
    attendance_rate = round(completed / attended_base * 100, 1) if attended_base > 0 else None

    return {
        "customer_count": customer_count,
        "booking_counts": {
            "total":     total_bookings,
            "completed": completed,
            "no_show":   no_show,
            "confirmed": confirmed,
            "requested": requested,
            "cancelled": cancelled,
        },
        "attendance_rate": attendance_rate,  # None if no completed/no_show data yet
    }


@router.get("/me/stats/customer/{customer_id}")
async def get_customer_stats(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """특정 고객의 출석 통계 (담당 강사만 조회 가능)"""
    instructor_id = UUID(str(user.id))

    # 해당 고객이 담당 고객인지 확인
    cust_res = await session.execute(
        select(User).where(
            and_(
                User.id == customer_id,
                User.manager_id == instructor_id,
                User.is_active == True,
            )
        )
    )
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="담당 고객을 찾을 수 없습니다.")

    # 상태별 집계
    booking_res = await session.execute(
        select(Booking.status, text("count(*) AS cnt"))
        .where(Booking.guest_id == customer_id)
        .group_by(Booking.status)
    )
    booking_counts: dict[str, int] = {}
    for row in booking_res:
        booking_counts[row.status] = row.cnt

    completed = booking_counts.get("COMPLETED", 0)
    no_show   = booking_counts.get("NO_SHOW", 0)
    attended_base = completed + no_show
    attendance_rate = round(completed / attended_base * 100, 1) if attended_base > 0 else None

    return {
        "customer_id": str(customer_id),
        "customer_name": customer.display_name,
        "booking_counts": {
            "total":     sum(booking_counts.values()),
            "completed": completed,
            "no_show":   no_show,
            "confirmed": booking_counts.get("CONFIRMED", 0),
            "requested": booking_counts.get("REQUESTED", 0),
            "cancelled": booking_counts.get("CANCELLED", 0),
        },
        "attendance_rate": attendance_rate,
    }
