from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.domains.posts.models import Post
from app.domains.posts.schemas import PostCreateAdmin, PostRead

router = APIRouter(tags=["Posts"])
admin_router = APIRouter(prefix="/admin", tags=["Admin Posts"])


# ---- 내부 헬퍼: content_manager가 특정 instructor 스코프인지 확인 ----
async def _is_staff_of_instructor(session: AsyncSession, *, instructor_id: str, staff_user_id: str) -> bool:
    res = await session.execute(
        text(
            """
            select 1
            from public.instructor_staff
            where instructor_id = :instructor_id
              and staff_user_id = :staff_user_id
            limit 1
            """
        ),
        {"instructor_id": instructor_id, "staff_user_id": staff_user_id},
    )
    return res.first() is not None


# -------------------------------------------------------------------
# 1) 운영/강사용: 회원 저장소에 게시물 생성
# POST /admin/posts
# -------------------------------------------------------------------
@admin_router.post(
    "/posts",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_post_admin(
    payload: PostCreateAdmin,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
):
    role = (user.role or "").upper()
    creator_id = UUID(str(user.id))

    instructor_id: UUID | None = payload.instructor_id

    # 권한 규칙:
    # - ADMIN: instructor_id 없어도 되고 아무 값도 가능
    # - INSTRUCTOR: instructor_id 없으면 본인으로 고정, 있으면 본인과 같아야 함
    # - CONTENT_MANAGER: instructor_id 필수 + 위임관계 있어야 함
    if role == "INSTRUCTOR":
        if instructor_id is None:
            instructor_id = UUID(str(user.id))
        elif str(instructor_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Instructor can create posts only in own scope")

    if role == "CONTENT_MANAGER":
        if instructor_id is None:
            raise HTTPException(status_code=400, detail="instructor_id is required for CONTENT_MANAGER")
        ok = await _is_staff_of_instructor(
            session,
            instructor_id=str(instructor_id),
            staff_user_id=str(user.id),
        )
        if not ok:
            raise HTTPException(status_code=403, detail="Not assigned to this instructor")

    post = Post(
        owner_user_id=payload.owner_user_id,
        created_by_user_id=creator_id,
        instructor_id=instructor_id,
        caption=payload.caption,
        status="PRIVATE",
        # updated_at은 DB default now()지만, 수정 시에는 코드에서 갱신해주면 더 좋음
    )

    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


# -------------------------------------------------------------------
# 2) 고객용: 내 저장소 목록
# GET /posts/me
# -------------------------------------------------------------------
@router.get(
    "/posts/me",
    response_model=list[PostRead],
)
async def list_my_posts(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    owner_id = UUID(str(user.id))
    stmt = (
        select(Post)
        .where(Post.owner_user_id == owner_id)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    return res.scalars().all()


# -------------------------------------------------------------------
# 3) 공개 피드
# GET /feed
# -------------------------------------------------------------------
@router.get(
    "/feed",
    response_model=list[PostRead],
)
async def public_feed(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # 공개 피드 정책: status=PUBLIC만
    stmt = (
        select(Post)
        .where(Post.status == "PUBLIC")
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    return res.scalars().all()

@router.post("/posts/{post_id}/consent/grant")
async def grant_public_consent(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    me = UUID(str(user.id))

    # post 조회 + owner 확인
    res = await session.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_user_id != me:
        raise HTTPException(status_code=403, detail="Only owner can grant public consent")

    # 상태 변경
    post.status = "PUBLIC"
    post.published_at = datetime.now(timezone.utc)
    post.updated_at = datetime.now(timezone.utc)
    session.add(post)

    # 로그 남기기
    await session.execute(
        text(
            """
            insert into public.post_consents (post_id, user_id, action)
            values (:post_id, :user_id, 'GRANT_PUBLIC')
            """
        ),
        {"post_id": str(post_id), "user_id": str(me)},
    )

    await session.commit()
    await session.refresh(post)
    return {"ok": True, "post_id": str(post.id), "status": post.status}


@router.post("/posts/{post_id}/consent/revoke")
async def revoke_public_consent(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    me = UUID(str(user.id))

    res = await session.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_user_id != me:
        raise HTTPException(status_code=403, detail="Only owner can revoke public consent")

    post.status = "PRIVATE"
    post.published_at = None
    post.updated_at = datetime.now(timezone.utc)
    session.add(post)

    await session.execute(
        text(
            """
            insert into public.post_consents (post_id, user_id, action)
            values (:post_id, :user_id, 'REVOKE_PUBLIC')
            """
        ),
        {"post_id": str(post_id), "user_id": str(me)},
    )

    await session.commit()
    await session.refresh(post)
    return {"ok": True, "post_id": str(post.id), "status": post.status}


# main.py에서 한 번에 include 할 수 있게 묶어서 export
router.include_router(admin_router)
