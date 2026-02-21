from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, CurrentUser
from app.core.config import settings
from app.db.session import get_session
from app.domains.instructor.schemas import (
    InstructorStaffCreate,
    InstructorStaffRead,
)

router = APIRouter(prefix="/instructors", tags=["Instructor"])


@router.post(
    "/me/staff",
    status_code=status.HTTP_201_CREATED,
)
async def add_staff(
    payload: InstructorStaffCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))

    res = await session.execute(
        text(
            """
            select id
            from public.users
            where email = :email
            """
        ),
        {"email": payload.staff_email},
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Staff user not found")

    staff_user_id = row[0]

    if str(staff_user_id) == str(instructor_id):
        raise HTTPException(status_code=400, detail="Cannot add yourself as staff")

    try:
        await session.execute(
            text(
                """
                insert into public.instructor_staff (instructor_id, staff_user_id)
                values (:instructor_id, :staff_user_id)
                """
            ),
            {
                "instructor_id": str(instructor_id),
                "staff_user_id": str(staff_user_id),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Staff already assigned")

    return {"ok": True}


@router.delete(
    "/me/staff/{staff_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_staff(
    staff_user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))

    res = await session.execute(
        text(
            """
            delete from public.instructor_staff
            where instructor_id = :instructor_id
              and staff_user_id = :staff_user_id
            """
        ),
        {
            "instructor_id": str(instructor_id),
            "staff_user_id": str(staff_user_id),
        },
    )

    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Staff relation not found")

    await session.commit()
    return None


@router.get(
    "/me/staff",
    response_model=list[InstructorStaffRead],
)
async def list_staff(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))

    res = await session.execute(
        text(
            """
            select
                u.id as staff_user_id,
                u.email,
                u.username,
                u.display_name,
                s.created_at
            from public.instructor_staff s
            join public.users u on u.id = s.staff_user_id
            where s.instructor_id = :instructor_id
            order by s.created_at desc
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


# 강사 신청/승인
@router.post("/apply")
async def apply_instructor(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """
    CUSTOMER → INSTRUCTOR 신청
    - role=INSTRUCTOR, status=PENDING
    - 승인 전에는 deps.require_role에서 INSTRUCTOR 기능 접근 차단됨
    """
    try:
        # 이미 신청했는지/강사인지 체크
        check = await session.execute(
            text(
                """
                select role, status
                from public.users
                where id = :user_id
                """
            ),
            {"user_id": str(user.id)},
        )
        row = check.first()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        current_role = (row.role or "").upper()
        current_status = (row.status or "ACTIVE").upper()

        if current_role == "INSTRUCTOR":
            # 이미 강사면 그대로 반환
            return {"ok": True, "role": current_role, "status": current_status}

        if current_role != "CUSTOMER":
            raise HTTPException(status_code=400, detail="Invalid role transition")

        res = await session.execute(
            text(
                """
                update public.users
                set role = 'INSTRUCTOR',
                    status = 'PENDING'
                where id = :user_id
                returning id, role, status
                """
            ),
            {"user_id": str(user.id)},
        )
        updated = res.first()
        await session.commit()
        return {"ok": True, "id": str(updated.id), "role": updated.role, "status": updated.status}
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to apply instructor")


@router.get("/pending")
async def list_pending_instructors(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """
    ADMIN: 승인 대기 강사 목록
    """
    res = await session.execute(
        text(
            """
            select id, email, username, display_name, created_at
            from public.users
            where role = 'INSTRUCTOR'
              and status = 'PENDING'
              and is_active = true
            order by created_at asc
            """
        )
    )
    rows = res.fetchall()
    return [
        {
            "id": str(r.id),
            "email": r.email,
            "username": r.username,
            "display_name": r.display_name,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/{user_id}/approve")
async def approve_instructor(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN"})),
):
    """
    ADMIN: 강사 승인
    - status를 ACTIVE로 변경
    """
    # 슈퍼어드민 보호
    if settings.SUPER_ADMIN_USER_ID and str(user_id) == str(settings.SUPER_ADMIN_USER_ID):
        raise HTTPException(status_code=403, detail="Cannot modify super admin")

    try:
        res = await session.execute(
            text(
                """
                update public.users
                set status = 'ACTIVE'
                where id = :target_id
                  and role = 'INSTRUCTOR'
                returning id, role, status
                """
            ),
            {"target_id": str(user_id)},
        )
        row = res.first()
        if not row:
            await session.rollback()
            raise HTTPException(status_code=404, detail="Pending instructor not found")

        await session.commit()
        return {"ok": True, "id": str(row.id), "role": row.role, "status": row.status}
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to approve instructor")