from __future__ import annotations

from typing import List, Optional 
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from app.core.auth.deps import CurrentUser, get_current_user, require_role, get_current_user_optional
from app.db.session import get_session
from app.domains.posts.models import Post, MediaType, PostType
from app.domains.posts.schemas import (
    PostCreate, PostResponse, PostMediaResponse, 
    CommentCreate, CommentResponse, PostUpdate, CommentUpdate, NotificationResponse
)
from app.domains.posts.repository import PostRepository
from app.core.s3 import upload_file_to_s3, create_presigned_url, delete_file_from_s3 

router = APIRouter(tags=["Posts"])
admin_router = APIRouter(prefix="/admin", tags=["Admin Posts"])

# 매니저 권한 확인 헬퍼
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

# S3 보안 URL 주입 헬퍼
def _inject_presigned_urls(post: Post) -> Post:
    if not post.media:
        return post
    
    for m in post.media:
        if m.s3_key_source:
            signed_url = create_presigned_url(m.s3_key_source)
            if signed_url:
                m.url = signed_url
    return post

# 게시물 생성 (관리자/강사 전용)
@admin_router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post_admin(
    payload: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
):
    role = (user.role or "").upper()
    target_instructor_id: UUID | None = payload.instructor_id

    if role == "INSTRUCTOR":
        if target_instructor_id is None:
            payload.instructor_id = UUID(str(user.id))
        elif str(target_instructor_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Instructor can create posts only in own scope")

    if role == "CONTENT_MANAGER":
        if target_instructor_id is None:
            raise HTTPException(status_code=400, detail="instructor_id is required for CONTENT_MANAGER")
        ok = await _is_staff_of_instructor(
            session,
            instructor_id=str(target_instructor_id),
            staff_user_id=str(user.id),
        )
        if not ok:
            raise HTTPException(status_code=403, detail="Not assigned to this instructor")

    repo = PostRepository(session)
    new_post = await repo.create(post_in=payload, created_by_user_id=UUID(str(user.id)))
    return new_post

# 게시물 수정 (관리자/강사/소유자 전용)
@admin_router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: UUID,
    payload: PostUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if user.role != "ADMIN" and post.owner_user_id != UUID(str(user.id)):
        raise HTTPException(status_code=403, detail="Not authorized to update this post")
        
    updated_post = await repo.update(post, payload)
    return _inject_presigned_urls(updated_post)

# 미디어 파일 업로드 및 S3 연동
@admin_router.post(
    "/posts/{post_id}/media",
    response_model=PostMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_post_media(
    post_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"})),
):
    repo = PostRepository(session)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if (user.role != "ADMIN") and (post.owner_user_id != UUID(str(user.id))):
         raise HTTPException(status_code=403, detail="Not authorized to upload media to this post")

    s3_result = upload_file_to_s3(file.file, file.filename, folder=str(post_id))
    if not s3_result:
        raise HTTPException(status_code=500, detail="Failed to upload file to S3")

    real_s3_url = s3_result["url"]
    real_s3_key = s3_result["key"]
    
    content_type = file.content_type or ""
    media_type = MediaType.VIDEO if "video" in content_type else MediaType.IMAGE

    media = await repo.add_media(
        post_id=post_id, 
        url=real_s3_url, 
        s3_key=real_s3_key, 
        media_type=media_type
    )
    return media

# 게시물 및 관련 S3 파일 삭제
@admin_router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"ADMIN", "INSTRUCTOR"})),
):
    stmt = select(Post).options(selectinload(Post.media)).where(Post.id == post_id)
    res = await session.execute(stmt)
    post = res.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if user.role != "ADMIN" and post.owner_user_id != UUID(str(user.id)):
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    for m in post.media:
        if m.s3_key_source:
            delete_file_from_s3(m.s3_key_source)

    await session.delete(post)
    await session.commit()
    return None

# 게시물 키워드 검색
@router.get("/search", response_model=List[PostResponse])
async def search_posts(
    q: Optional[str] = Query(None, min_length=2),
    post_type: Optional[PostType] = None,
    session: AsyncSession = Depends(get_session),
):
    repo = PostRepository(session)
    posts = await repo.search_posts(keyword=q, post_type=post_type)
    return [_inject_presigned_urls(p) for p in posts]

# 내 게시물 목록 조회
@router.get(
    "/posts/me",
    response_model=list[PostResponse],
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
        .options(selectinload(Post.media)) 
        .where(Post.owner_user_id == owner_id)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    posts = res.scalars().all()
    return [_inject_presigned_urls(p) for p in posts]

# 공개 피드 조회
@router.get(
    "/feed",
    response_model=list[PostResponse],
)
async def public_feed(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.media))
        .where(Post.status == "PUBLIC")
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    posts = res.scalars().all()
    return [_inject_presigned_urls(p) for p in posts]

# 게시물 상세 조회
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser | None = Depends(get_current_user_optional),
):
    repo = PostRepository(session)
    user_id = UUID(str(user.id)) if user else None
    post = await repo.get_post_with_counts(post_id, user_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    has_access = False
    if post.status == "PUBLIC":
        has_access = True
    elif user:
        role = (user.role or "").upper()
        if post.owner_user_id == user_id or role == "ADMIN":
            has_access = True
        elif post.instructor_id is not None and str(post.instructor_id) == str(user_id):
            has_access = True

    if not has_access:
        if not user:
             raise HTTPException(status_code=401, detail="Authentication required")
        raise HTTPException(status_code=403, detail="Not allowed to view this post")

    return _inject_presigned_urls(post)

# 댓글 작성
@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: UUID,
    payload: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    is_public = (post.status == "PUBLIC")
    is_owner = (post.owner_user_id == UUID(str(user.id)))
    is_admin = (user.role == "ADMIN")
    
    if not (is_public or is_owner or is_admin):
         raise HTTPException(status_code=403, detail="Cannot comment on private post")

    comment = await repo.create_comment(post_id, UUID(str(user.id)), payload)
    return comment

# 댓글 수정
@router.patch("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: UUID,
    payload: CommentUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    comment = await repo.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if comment.user_id != UUID(str(user.id)):
        raise HTTPException(status_code=403, detail="Only owner can update comment")
        
    return await repo.update_comment(comment_id, payload)

# 게시물별 댓글 목록 조회
@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    repo = PostRepository(session)
    comments = await repo.get_comments_by_post(post_id, skip, limit)
    return comments

# 댓글 삭제
@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    comment = await repo.get_comment_by_id(comment_id)
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if comment.user_id != UUID(str(user.id)) and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await repo.delete_comment(comment_id)
    return None

# 좋아요 토글
@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    is_liked = await repo.toggle_like(post_id, UUID(str(user.id)))
    return {"ok": True, "is_liked": is_liked}

# 공개 권한 부여
@router.post("/posts/{post_id}/consent/grant")
async def grant_public_consent(
    post_id: UUID, 
    session: AsyncSession = Depends(get_session), 
    user: CurrentUser = Depends(get_current_user)
):
    me = UUID(str(user.id))
    res = await session.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    
    if not post: 
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_user_id != me: 
        raise HTTPException(status_code=403, detail="Only owner can grant public consent")
    
    now = datetime.now(timezone.utc)
    post.status = "PUBLIC"
    post.published_at = now
    post.updated_at = now
    post.is_consent_given = True 
    
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return {"ok": True, "post_id": str(post.id), "status": post.status}

# 공개 권한 철회
@router.post("/posts/{post_id}/consent/revoke")
async def revoke_public_consent(
    post_id: UUID, 
    session: AsyncSession = Depends(get_session), 
    user: CurrentUser = Depends(get_current_user)
):
    me = UUID(str(user.id))
    res = await session.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    
    if not post: 
        raise HTTPException(status_code=404, detail="Post not found")
    if post.owner_user_id != me: 
        raise HTTPException(status_code=403, detail="Only owner can revoke public consent")
    
    now = datetime.now(timezone.utc)
    post.status = "PRIVATE"
    post.published_at = None
    post.updated_at = now
    post.is_consent_given = False
    
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return {"ok": True, "post_id": str(post.id), "status": post.status}

# 내 알림 목록 조회
@router.get("/notifications", response_model=List[NotificationResponse])
async def list_my_notifications(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    repo = PostRepository(session)
    notifications = await repo.get_my_notifications(UUID(str(user.id)), skip, limit)
    return notifications

# 알림 읽음 처리
@router.patch("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    success = await repo.mark_notification_as_read(UUID(str(user.id)), notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found or access denied")
    return {"ok": True}

router.include_router(admin_router)