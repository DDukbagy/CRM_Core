from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
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

    # staff 유저 찾기
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

    # 자기 자신 추가 방지
    if str(staff_user_id) == str(instructor_id):
        raise HTTPException(status_code=400, detail="Cannot add yourself as staff")

    # 위임 관계 생성
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
