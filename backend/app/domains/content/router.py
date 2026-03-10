from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.db.session import get_session
from app.domains.content.models import InstructorPost
from app.domains.content.schemas import PostCreate, PostRead, PostUpdate
from app.domains.users.models import User

router = APIRouter(prefix="/instructor-posts", tags=["Instructor Posts"])


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 게시물(프로모션/피드백) 생성."""
    instructor_id = UUID(str(user.id))

    if data.type not in ("PROMOTION", "FEEDBACK"):
        raise HTTPException(status_code=400, detail="type은 PROMOTION 또는 FEEDBACK이어야 합니다.")

    if data.type == "FEEDBACK":
        if not data.customer_id:
            raise HTTPException(status_code=400, detail="FEEDBACK 게시물은 customer_id가 필요합니다.")
        # 담당 고객인지 확인
        cust_res = await session.execute(select(User).where(User.id == data.customer_id))
        customer = cust_res.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        if user.role == "INSTRUCTOR" and customer.manager_id != instructor_id:
            raise HTTPException(status_code=403, detail="담당 고객의 피드백만 등록할 수 있습니다.")
        # 고객 동의 여부에 따라 공개 여부 강제
        has_consent = getattr(customer, "feedback_consent", False) or False
        is_public = data.is_public and has_consent
    else:
        # PROMOTION은 강사가 공개 여부 결정
        is_public = data.is_public

    post = InstructorPost(
        instructor_id=instructor_id,
        type=data.type,
        title=data.title,
        content=data.content,
        media_url=data.media_url,
        customer_id=data.customer_id,
        is_public=is_public,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


@router.get("", response_model=list[PostRead])
async def list_posts(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
):
    """게시물 목록. INSTRUCTOR: 본인 게시물. CUSTOMER: 공개 + 자기 관련 게시물."""
    uid = UUID(str(user.id))
    stmt = select(InstructorPost)

    if user.role == "INSTRUCTOR":
        stmt = stmt.where(InstructorPost.instructor_id == uid)
        if customer_id:
            stmt = stmt.where(InstructorPost.customer_id == customer_id)
    elif user.role == "CUSTOMER":
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                InstructorPost.is_public == True,
                InstructorPost.customer_id == uid,
            )
        )
    # ADMIN: all

    stmt = stmt.order_by(InstructorPost.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    uid = UUID(str(user.id))
    if user.role == "INSTRUCTOR" and post.instructor_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.role == "CUSTOMER" and not post.is_public and post.customer_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    return post


@router.patch("/{post_id}", response_model=PostRead)
async def update_post(
    post_id: UUID,
    data: PostUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    uid = UUID(str(user.id))
    if user.role == "INSTRUCTOR" and post.instructor_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    patch = data.model_dump(exclude_unset=True)
    # FEEDBACK + is_public=True → check consent again
    if "is_public" in patch and patch["is_public"] and post.type == "FEEDBACK" and post.customer_id:
        cust_res = await session.execute(select(User).where(User.id == post.customer_id))
        customer = cust_res.scalar_one_or_none()
        if not customer or not getattr(customer, "feedback_consent", False):
            patch["is_public"] = False

    for field, value in patch.items():
        setattr(post, field, value)

    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    uid = UUID(str(user.id))
    if user.role == "INSTRUCTOR" and post.instructor_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    await session.delete(post)
    await session.commit()
    return None


@router.patch("/customers/{customer_id}/feedback-consent", status_code=200)
async def toggle_feedback_consent(
    customer_id: UUID,
    consent: bool,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """고객 피드백 공개 동의 설정 (강사가 고객 동의를 받은 후 활성화)."""
    uid = UUID(str(user.id))
    cust_res = await session.execute(select(User).where(User.id == customer_id))
    customer = cust_res.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if user.role == "INSTRUCTOR" and customer.manager_id != uid:
        raise HTTPException(status_code=403, detail="담당 고객만 설정할 수 있습니다.")

    customer.feedback_consent = consent
    session.add(customer)
    await session.commit()
    return {"ok": True, "customer_id": str(customer_id), "feedback_consent": consent}
