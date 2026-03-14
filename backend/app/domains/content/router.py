from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

import uuid as _uuid
from app.core.auth.deps import get_current_user, require_role, CurrentUser
from app.core.s3 import create_presigned_post, BUCKET_NAME, REGION, MAX_IMAGE_BYTES, MAX_VIDEO_BYTES
from app.db.session import get_session
from app.domains.content.models import InstructorPost, InstructorPostMedia, PostComment
from app.domains.content.schemas import (
    PostCreate, PostRead, PostUpdate, MediaItemRead,
    UploadUrlRequest, UploadUrlResponse,
    CommentCreate, CommentRead,
)
from app.domains.users.models import User

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime",
}

router = APIRouter(prefix="/instructor-posts", tags=["Instructor Posts"])


# ─── 헬퍼 ─────────────────────────────────────────────────────────────────────

async def _load_media(session: AsyncSession, post_id: UUID) -> list[MediaItemRead]:
    res = await session.execute(
        select(InstructorPostMedia).where(InstructorPostMedia.post_id == post_id).order_by(InstructorPostMedia.sort_order)
    )
    return [MediaItemRead.model_validate(m) for m in res.scalars().all()]


async def _replace_media(session: AsyncSession, post_id: UUID, items: list) -> None:
    existing = await session.execute(select(InstructorPostMedia).where(InstructorPostMedia.post_id == post_id))
    for m in existing.scalars().all():
        await session.delete(m)
    for item in items:
        session.add(InstructorPostMedia(post_id=post_id, url=item.url, media_type=item.media_type, sort_order=item.sort_order))


async def _to_post_read(session: AsyncSession, post: InstructorPost) -> PostRead:
    pr = PostRead.model_validate(post)
    pr.media_items = await _load_media(session, post.id)
    if post.customer_id:
        cu = await session.get(User, post.customer_id)
        pr.customer_name = cu.display_name if cu else str(post.customer_id)
    return pr


async def _check_post_access(post: InstructorPost, user: CurrentUser) -> None:
    uid = UUID(str(user.id))
    if user.role == "INSTRUCTOR" and post.instructor_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.role == "CUSTOMER" and not post.is_public and post.customer_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")


# ─── S3 업로드 URL ────────────────────────────────────────────────────────────

@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    req: UploadUrlRequest,
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    if req.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식: {req.content_type}")

    is_video = req.content_type.startswith("video/")
    max_bytes = MAX_VIDEO_BYTES if is_video else MAX_IMAGE_BYTES

    ext = req.filename.rsplit(".", 1)[-1].lower() if "." in req.filename else "bin"
    key = f"instructor-posts/{user.id}/{_uuid.uuid4()}.{ext}"

    result = create_presigned_post(key, req.content_type, max_bytes)
    if not result:
        raise HTTPException(status_code=500, detail="S3 presigned URL 생성 실패")

    public_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{key}"
    return UploadUrlResponse(
        upload_url=result["url"],
        fields=result["fields"],
        key=key,
        public_url=public_url,
    )


# ─── 게시물 CRUD ──────────────────────────────────────────────────────────────

@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    instructor_id = UUID(str(user.id))

    if data.type not in ("PROMOTION", "FEEDBACK"):
        raise HTTPException(status_code=400, detail="type은 PROMOTION 또는 FEEDBACK이어야 합니다.")

    if data.type == "FEEDBACK":
        if not data.customer_id:
            raise HTTPException(status_code=400, detail="FEEDBACK 게시물은 customer_id가 필요합니다.")
        cust_res = await session.execute(select(User).where(User.id == data.customer_id))
        customer = cust_res.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        if user.role == "INSTRUCTOR" and customer.manager_id != instructor_id:
            raise HTTPException(status_code=403, detail="담당 고객의 피드백만 등록할 수 있습니다.")
        has_consent = getattr(customer, "feedback_consent", False) or False
        is_public = has_consent  # 동의하면 공개, 아니면 비공개
    else:
        is_public = True  # PROMOTION은 항상 공개

    post = InstructorPost(
        instructor_id=instructor_id,
        type=data.type,
        title=data.title,
        content=data.content,
        customer_id=data.customer_id,
        is_public=is_public,
    )
    session.add(post)
    await session.flush()  # id 확보

    for item in data.media_items:
        session.add(InstructorPostMedia(post_id=post.id, url=item.url, media_type=item.media_type, sort_order=item.sort_order))

    await session.commit()
    await session.refresh(post)
    return await _to_post_read(session, post)


@router.get("", response_model=list[PostRead])
async def list_posts(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    uid = UUID(str(user.id))
    stmt = select(InstructorPost)

    if user.role == "INSTRUCTOR":
        stmt = stmt.where(InstructorPost.instructor_id == uid)
        if customer_id:
            stmt = stmt.where(InstructorPost.customer_id == customer_id)
    elif user.role == "CUSTOMER":
        stmt = stmt.where(or_(InstructorPost.is_public == True, InstructorPost.customer_id == uid))

    stmt = stmt.order_by(InstructorPost.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    posts = result.scalars().all()

    # N+1 방지: customer_id가 있는 포스트들의 유저를 한 번에 조회
    customer_ids = list({p.customer_id for p in posts if p.customer_id})
    customer_map: dict = {}
    if customer_ids:
        cu_res = await session.execute(select(User).where(User.id.in_(customer_ids)))
        customer_map = {str(u.id): u.display_name for u in cu_res.scalars().all()}

    result_list = []
    for p in posts:
        pr = PostRead.model_validate(p)
        pr.media_items = await _load_media(session, p.id)
        if p.customer_id:
            pr.customer_name = customer_map.get(str(p.customer_id), str(p.customer_id))
        result_list.append(pr)
    return result_list


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await _check_post_access(post, user)
    return await _to_post_read(session, post)


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

    if data.title is not None:
        post.title = data.title
    if data.content is not None:
        post.content = data.content

    # 미디어 교체
    if data.media_items is not None:
        await _replace_media(session, post_id, data.media_items)

    session.add(post)
    await session.commit()
    await session.refresh(post)
    return await _to_post_read(session, post)


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


# ─── 댓글 ─────────────────────────────────────────────────────────────────────

@router.get("/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await _check_post_access(post, user)

    result = await session.execute(
        select(PostComment).where(PostComment.post_id == post_id).order_by(PostComment.created_at)
    )
    comments = result.scalars().all()

    user_ids = list({c.user_id for c in comments})
    user_map: dict[UUID, str] = {}
    if user_ids:
        u_res = await session.execute(select(User).where(User.id.in_(user_ids)))
        user_map = {u.id: u.display_name for u in u_res.scalars().all()}

    return [
        CommentRead(
            id=c.id, post_id=c.post_id, user_id=c.user_id,
            user_name=user_map.get(c.user_id) or str(c.user_id),
            content=c.content, created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: UUID,
    data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    post = await session.get(InstructorPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await _check_post_access(post, user)

    uid = UUID(str(user.id))
    comment = PostComment(post_id=post_id, user_id=uid, content=data.content)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    u = await session.get(User, uid)
    return CommentRead(
        id=comment.id, post_id=comment.post_id, user_id=comment.user_id,
        user_name=u.display_name if u else str(uid),
        content=comment.content, created_at=comment.created_at,
    )


# ─── 피드백 동의 ──────────────────────────────────────────────────────────────

@router.patch("/customers/{customer_id}/feedback-consent", status_code=200)
async def toggle_feedback_consent(
    customer_id: UUID,
    consent: bool,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
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
