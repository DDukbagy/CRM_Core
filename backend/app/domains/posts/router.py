from __future__ import annotations

import uuid as _uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser, get_current_user, get_current_user_optional, require_role
from app.core.s3 import (
    BUCKET_NAME, REGION, create_presigned_upload_url, create_presigned_url, delete_file_from_s3,
)
from app.db.session import get_session
from app.domains.posts.models import Post, PostComment
from app.domains.posts.repository import PostRepository, WRITER_ROLES
from app.domains.posts.schemas import (
    PostCreate, PostRead, PostUpdate, MediaItemRead,
    UploadUrlRequest, UploadUrlResponse,
    CommentCreate, CommentRead, CommentUpdate, DELETED_COMMENT_TEXT,
)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime",
}

router = APIRouter(prefix="/posts", tags=["Posts"])


# ─── 응답 변환 ────────────────────────────────────────────────────────────────

async def _to_post_reads(
    repo: PostRepository, posts: list[Post], user: Optional[CurrentUser]
) -> list[PostRead]:
    post_ids = [p.id for p in posts]
    user_id = UUID(str(user.id)) if user else None

    media_map = await repo.media_by_post(post_ids)
    name_map = await repo.display_names(list({p.customer_id for p in posts if p.customer_id}))
    like_map, comment_map, liked_set = await repo.counts(post_ids, user_id)

    result: list[PostRead] = []
    for p in posts:
        pr = PostRead.model_validate(p)
        items: list[MediaItemRead] = []
        for m in media_map.get(p.id, []):
            item = MediaItemRead.model_validate(m)
            # S3 객체는 조회할 때마다 임시 서명 URL로 내려준다 (발급 실패 시 저장된 주소 유지)
            if m.s3_key:
                item.url = create_presigned_url(m.s3_key) or m.url
            items.append(item)
        pr.media_items = items
        if p.customer_id:
            pr.customer_name = name_map.get(p.customer_id, str(p.customer_id))
        pr.like_count = like_map.get(p.id, 0)
        pr.comment_count = comment_map.get(p.id, 0)
        pr.is_liked = p.id in liked_set
        result.append(pr)
    return result


async def _to_post_read(repo: PostRepository, post: Post, user: Optional[CurrentUser]) -> PostRead:
    return (await _to_post_reads(repo, [post], user))[0]


async def _to_comment_reads(repo: PostRepository, comments: list[PostComment]) -> list[CommentRead]:
    name_map = await repo.display_names(list({c.user_id for c in comments}))
    result: list[CommentRead] = []
    for c in comments:
        deleted = c.deleted_at is not None
        result.append(
            CommentRead(
                id=c.id, post_id=c.post_id, user_id=c.user_id,
                user_name=None if deleted else (name_map.get(c.user_id) or str(c.user_id)),
                parent_id=c.parent_id,
                content=DELETED_COMMENT_TEXT if deleted else c.content,
                created_at=c.created_at, updated_at=c.updated_at,
                is_deleted=deleted,
            )
        )
    return result


# ─── S3 업로드 URL ────────────────────────────────────────────────────────────

@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    req: UploadUrlRequest,
    user: CurrentUser = Depends(require_role(WRITER_ROLES)),
):
    if req.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식: {req.content_type}")

    ext = req.filename.rsplit(".", 1)[-1].lower() if "." in req.filename else "bin"
    # S3 키 접두사는 기존 객체·버킷 정책과 맞추기 위해 그대로 둔다
    key = f"instructor-posts/{user.id}/{_uuid.uuid4()}.{ext}"

    # presigned PUT — FormData 없이 직접 PUT, RN에서 더 안정적
    upload_url = create_presigned_upload_url(key, req.content_type)
    if not upload_url:
        raise HTTPException(status_code=500, detail="S3 presigned URL 생성 실패")

    public_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{key}"
    return UploadUrlResponse(
        upload_url=upload_url,
        key=key,
        public_url=public_url,
    )


# ─── 게시물 목록 (고정 경로는 /{post_id} 보다 먼저 등록) ──────────────────────

# 역할별 목록: 강사는 본인 글, 고객은 공개 글 + 본인 피드백
@router.get("", response_model=list[PostRead])
async def list_posts(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    customer_id: UUID | None = None,
    type: str | None = Query(None, description="PROMOTION, NOTICE, FEEDBACK or COMMUNITY"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    repo = PostRepository(session)
    posts = await repo.list_for_user(user, customer_id=customer_id, type=type, limit=limit, offset=offset)
    return await _to_post_reads(repo, posts, user)


# 공개 피드 (비로그인 가능)
@router.get("/feed", response_model=list[PostRead])
async def public_feed(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser | None = Depends(get_current_user_optional),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    repo = PostRepository(session)
    posts = await repo.list_public(limit=limit, offset=offset)
    return await _to_post_reads(repo, posts, user)


# 공개 게시물 키워드 검색 (비로그인 가능)
@router.get("/search", response_model=list[PostRead])
async def search_posts(
    q: Optional[str] = Query(None, min_length=2),
    type: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser | None = Depends(get_current_user_optional),
):
    repo = PostRepository(session)
    posts = await repo.search_public(keyword=q, type=type)
    return await _to_post_reads(repo, posts, user)


# 내 게시물 목록
@router.get("/me", response_model=list[PostRead])
async def list_my_posts(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    repo = PostRepository(session)
    posts = await repo.list_mine(UUID(str(user.id)), limit=limit, offset=offset)
    return await _to_post_reads(repo, posts, user)


# ─── 댓글 수정·삭제 (댓글 ID 기준) ────────────────────────────────────────────

@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    comment = await repo.get_comment_or_404(comment_id)
    comment = await repo.update_comment(comment, user, payload.content)
    return (await _to_comment_reads(repo, [comment]))[0]


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    comment = await repo.get_comment_or_404(comment_id)
    await repo.delete_comment(comment, user)
    return None


# ─── 게시물 CRUD ──────────────────────────────────────────────────────────────

@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(WRITER_ROLES)),
):
    repo = PostRepository(session)
    post = await repo.create(data, user)
    return await _to_post_read(repo, post, user)


# 게시물 상세 (공개 글은 비로그인 가능)
@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser | None = Depends(get_current_user_optional),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    repo.ensure_can_view(post, user)
    return await _to_post_read(repo, post, user)


@router.patch("/{post_id}", response_model=PostRead)
async def update_post(
    post_id: UUID,
    data: PostUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(WRITER_ROLES)),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    post = await repo.update(post, data, user)
    return await _to_post_read(repo, post, user)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(WRITER_ROLES)),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    s3_keys = await repo.delete(post, user)
    for key in s3_keys:
        delete_file_from_s3(key)
    return None


# ─── 댓글 ─────────────────────────────────────────────────────────────────────

@router.get("/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    repo.ensure_can_view(post, user)
    return await _to_comment_reads(repo, await repo.list_comments(post_id))


@router.post("/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: UUID,
    data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    repo.ensure_can_view(post, user)
    comment = await repo.create_comment(post, UUID(str(user.id)), data)
    return (await _to_comment_reads(repo, [comment]))[0]


# ─── 좋아요 ───────────────────────────────────────────────────────────────────

@router.post("/{post_id}/like")
async def toggle_like(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    repo.ensure_can_view(post, user)
    is_liked = await repo.toggle_like(post, UUID(str(user.id)))
    return {"ok": True, "is_liked": is_liked}


# ─── 피드백 공개 동의 (대상 고객) ─────────────────────────────────────────────

@router.post("/{post_id}/consent/grant")
async def grant_public_consent(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    post = await repo.set_feedback_consent(post, user, granted=True)
    return {"ok": True, "post_id": str(post.id), "is_public": post.is_public}


@router.post("/{post_id}/consent/revoke")
async def revoke_public_consent(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = PostRepository(session)
    post = await repo.get_or_404(post_id)
    post = await repo.set_feedback_consent(post, user, granted=False)
    return {"ok": True, "post_id": str(post.id), "is_public": post.is_public}
