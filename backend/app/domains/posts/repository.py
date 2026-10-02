from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser
from app.domains.instructor.models import InstructorStaff
from app.domains.notifications.models import NotificationType
from app.domains.notifications.repository import NotificationRepository
from app.domains.posts.models import Post, PostMedia, PostComment, PostLike, PostType
from app.domains.posts.schemas import PostCreate, PostUpdate, CommentCreate, MediaItemCreate
from app.domains.users.models import User

WRITER_ROLES = {"INSTRUCTOR", "CONTENT_MANAGER", "ADMIN"}


def s3_key_from_url(url: str) -> Optional[str]:
    """S3 주소(공개 주소·임시 서명 주소 모두)에서 객체 키를 뽑는다. S3 주소가 아니면 None."""
    parsed = urlparse(url)
    if not parsed.hostname or not parsed.hostname.endswith(".amazonaws.com"):
        return None
    key = unquote(parsed.path.lstrip("/"))
    return key or None


def canonical_media_url(url: str) -> str:
    """임시 서명 주소로 들어와도 서명(쿼리)을 뗀 주소만 저장한다."""
    if s3_key_from_url(url) is None:
        return url
    return url.split("?", 1)[0]


class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        # 같은 세션을 공유해 알림 생성이 게시물 쪽 트랜잭션과 함께 커밋되게 한다
        self.notifications = NotificationRepository(session)

    # ── 조회 ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, post_id: UUID) -> Optional[Post]:
        return await self.session.get(Post, post_id)

    async def get_or_404(self, post_id: UUID) -> Post:
        post = await self.get_by_id(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return post

    # 역할별 목록: 강사는 본인 글, 고객은 공개 글 + 본인 피드백, 그 외(관리자 등)는 전체
    async def list_for_user(
        self,
        user: CurrentUser,
        customer_id: Optional[UUID] = None,
        type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Post]:
        uid = UUID(str(user.id))
        stmt = select(Post)

        if user.role == "INSTRUCTOR":
            stmt = stmt.where(Post.instructor_id == uid)
            if customer_id:
                stmt = stmt.where(Post.customer_id == customer_id)
        elif user.role == "CUSTOMER":
            if type == PostType.FEEDBACK.value:
                stmt = stmt.where(Post.customer_id == uid)
            else:
                stmt = stmt.where(or_(Post.is_public == True, Post.customer_id == uid))

        if type:
            stmt = stmt.where(Post.type == type)

        stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    # 내가 주인이거나 내가 작성한 게시물
    async def list_mine(self, user_id: UUID, limit: int = 50, offset: int = 0) -> list[Post]:
        stmt = (
            select(Post)
            .where(or_(Post.instructor_id == user_id, Post.created_by_user_id == user_id))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # 공개 피드
    async def list_public(self, limit: int = 50, offset: int = 0) -> list[Post]:
        stmt = (
            select(Post)
            .where(Post.is_public == True)
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # 공개 게시물 키워드 검색 및 종류 필터
    async def search_public(
        self, keyword: Optional[str] = None, type: Optional[str] = None, skip: int = 0, limit: int = 50
    ) -> list[Post]:
        stmt = select(Post).where(Post.is_public == True)
        if keyword:
            stmt = stmt.where(or_(Post.title.ilike(f"%{keyword}%"), Post.content.ilike(f"%{keyword}%")))
        if type:
            stmt = stmt.where(Post.type == type)
        stmt = stmt.order_by(desc(Post.created_at)).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    # ── 접근 규칙 ─────────────────────────────────────────────────────────────

    def can_view(self, post: Post, user: Optional[CurrentUser]) -> bool:
        if post.is_public:
            return True
        if user is None:
            return False
        uid = UUID(str(user.id))
        if user.role == "ADMIN":
            return True
        return uid in (post.instructor_id, post.created_by_user_id, post.customer_id)

    def ensure_can_view(self, post: Post, user: Optional[CurrentUser]) -> None:
        if self.can_view(post, user):
            return
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        raise HTTPException(status_code=403, detail="Forbidden")

    def ensure_can_manage(self, post: Post, user: CurrentUser) -> None:
        uid = UUID(str(user.id))
        if user.role == "ADMIN" or uid in (post.instructor_id, post.created_by_user_id):
            return
        raise HTTPException(status_code=403, detail="Forbidden")

    async def _is_staff_of_instructor(self, instructor_id: UUID, staff_user_id: UUID) -> bool:
        res = await self.session.execute(
            select(InstructorStaff.id).where(
                InstructorStaff.instructor_id == instructor_id,
                InstructorStaff.staff_user_id == staff_user_id,
            ).limit(1)
        )
        return res.first() is not None

    # ── 게시물 작성·수정·삭제 ─────────────────────────────────────────────────

    async def create(self, data: PostCreate, user: CurrentUser) -> Post:
        uid = UUID(str(user.id))
        role = (user.role or "").upper()
        if role not in WRITER_ROLES:
            raise HTTPException(status_code=403, detail="Forbidden")

        allowed_types = {t.value for t in PostType}
        if data.type not in allowed_types:
            raise HTTPException(
                status_code=400, detail="type은 PROMOTION, NOTICE, FEEDBACK, COMMUNITY 중 하나여야 합니다."
            )

        # 게시물 주인 결정
        if role == "CONTENT_MANAGER":
            if data.instructor_id is None:
                raise HTTPException(status_code=400, detail="instructor_id is required for CONTENT_MANAGER")
            if not await self._is_staff_of_instructor(data.instructor_id, uid):
                raise HTTPException(status_code=403, detail="Not assigned to this instructor")
            owner_id = data.instructor_id
        elif role == "INSTRUCTOR":
            if data.instructor_id is not None and data.instructor_id != uid:
                raise HTTPException(status_code=403, detail="Instructor can create posts only in own scope")
            owner_id = uid
        else:  # ADMIN
            owner_id = data.instructor_id or uid

        if data.type == PostType.FEEDBACK.value:
            if not data.customer_id:
                raise HTTPException(status_code=400, detail="FEEDBACK 게시물은 customer_id가 필요합니다.")
            customer = await self.session.get(User, data.customer_id)
            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")
            if role != "ADMIN" and customer.manager_id != owner_id:
                raise HTTPException(status_code=403, detail="담당 고객의 피드백만 등록할 수 있습니다.")
            is_public = False  # FEEDBACK은 비공개로 시작 (대상 고객이 동의하면 공개)
        else:
            is_public = True  # PROMOTION / NOTICE / COMMUNITY 는 공개

        post = Post(
            instructor_id=owner_id,
            created_by_user_id=uid,
            type=data.type,
            title=data.title,
            content=data.content,
            customer_id=data.customer_id,
            is_public=is_public,
        )
        self.session.add(post)
        await self.session.flush()  # id 확보
        self._add_media(post.id, data.media_items)

        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def update(self, post: Post, data: PostUpdate, user: CurrentUser) -> Post:
        self.ensure_can_manage(post, user)

        if data.title is not None:
            post.title = data.title
        if data.content is not None:
            post.content = data.content

        # 미디어 교체
        if data.media_items is not None:
            existing = await self.session.execute(select(PostMedia).where(PostMedia.post_id == post.id))
            for m in existing.scalars().all():
                await self.session.delete(m)
            self._add_media(post.id, data.media_items)

        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def delete(self, post: Post, user: CurrentUser) -> list[str]:
        """게시물을 지우고, 함께 지워야 할 S3 객체 키 목록을 돌려준다."""
        self.ensure_can_manage(post, user)
        res = await self.session.execute(
            select(PostMedia.s3_key).where(PostMedia.post_id == post.id, PostMedia.s3_key.is_not(None))
        )
        keys = [k for (k,) in res.all()]
        await self.notifications.delete_for_post(post.id)
        await self.session.delete(post)
        await self.session.commit()
        return keys

    def _add_media(self, post_id: UUID, items: list[MediaItemCreate]) -> None:
        for item in items:
            self.session.add(
                PostMedia(
                    post_id=post_id,
                    url=canonical_media_url(item.url),
                    s3_key=s3_key_from_url(item.url),
                    media_type=item.media_type,
                    sort_order=item.sort_order,
                )
            )

    # ── 공개 동의 (피드백 대상 고객만) ────────────────────────────────────────

    async def set_feedback_consent(self, post: Post, user: CurrentUser, granted: bool) -> Post:
        if post.type != PostType.FEEDBACK.value:
            raise HTTPException(status_code=400, detail="공개 동의는 FEEDBACK 게시물에만 적용됩니다.")
        if post.customer_id is None or post.customer_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail="피드백 대상 고객만 공개 동의를 변경할 수 있습니다.")

        post.is_public = granted
        post.updated_at = datetime.now(timezone.utc)
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    # ── 응답 조립용 부가 정보 (N+1 없이 한 번에) ──────────────────────────────

    async def media_by_post(self, post_ids: list[UUID]) -> dict[UUID, list[PostMedia]]:
        result: dict[UUID, list[PostMedia]] = {pid: [] for pid in post_ids}
        if not post_ids:
            return result
        res = await self.session.execute(
            select(PostMedia).where(PostMedia.post_id.in_(post_ids)).order_by(PostMedia.sort_order, PostMedia.id)
        )
        for m in res.scalars().all():
            result[m.post_id].append(m)
        return result

    async def display_names(self, user_ids: list[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        res = await self.session.execute(select(User.id, User.display_name).where(User.id.in_(user_ids)))
        return {r.id: r.display_name for r in res}

    async def counts(
        self, post_ids: list[UUID], user_id: Optional[UUID] = None
    ) -> tuple[dict[UUID, int], dict[UUID, int], set[UUID]]:
        """(좋아요 수, 댓글 수, 내가 좋아요 한 게시물) 을 돌려준다."""
        if not post_ids:
            return {}, {}, set()

        like_rows = await self.session.execute(
            select(PostLike.post_id, func.count().label("cnt"))
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id)
        )
        like_map: dict[UUID, int] = {r.post_id: r.cnt for r in like_rows}

        comment_rows = await self.session.execute(
            select(PostComment.post_id, func.count().label("cnt"))
            .where(PostComment.post_id.in_(post_ids), PostComment.deleted_at.is_(None))
            .group_by(PostComment.post_id)
        )
        comment_map: dict[UUID, int] = {r.post_id: r.cnt for r in comment_rows}

        liked_set: set[UUID] = set()
        if user_id:
            liked_rows = await self.session.execute(
                select(PostLike.post_id).where(PostLike.post_id.in_(post_ids), PostLike.user_id == user_id)
            )
            liked_set = {r.post_id for r in liked_rows}

        return like_map, comment_map, liked_set

    # ── 댓글 ──────────────────────────────────────────────────────────────────

    async def list_comments(self, post_id: UUID, skip: int = 0, limit: int = 200) -> list[PostComment]:
        res = await self.session.execute(
            select(PostComment)
            .where(PostComment.post_id == post_id)
            .order_by(PostComment.created_at, PostComment.id)
            .offset(skip)
            .limit(limit)
        )
        return list(res.scalars().all())

    # 수정·삭제 대상 조회. 이미 삭제된 댓글은 없는 것으로 본다
    async def get_comment_or_404(self, comment_id: int) -> PostComment:
        comment = await self.session.get(PostComment, comment_id)
        if not comment or comment.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Comment not found")
        return comment

    @staticmethod
    def _comment_notification_message(content: str) -> str:
        return f"내 게시글에 댓글이 달렸습니다: {content[:20]}"

    # 댓글 작성 및 알림 생성
    async def create_comment(self, post: Post, user_id: UUID, payload: CommentCreate) -> PostComment:
        if payload.parent_id is not None:
            parent = await self.session.get(PostComment, payload.parent_id)
            if not parent or parent.post_id != post.id:
                raise HTTPException(status_code=400, detail="parent_id가 이 게시물의 댓글이 아닙니다.")
            if parent.deleted_at is not None:
                raise HTTPException(status_code=400, detail="삭제된 댓글에는 답글을 달 수 없습니다.")

        comment = PostComment(
            post_id=post.id, user_id=user_id, content=payload.content, parent_id=payload.parent_id
        )
        self.session.add(comment)

        if post.instructor_id != user_id:
            n_type = NotificationType.REPLY if payload.parent_id else NotificationType.COMMENT
            msg = self._comment_notification_message(payload.content)
            await self.notifications.create_notification(post.instructor_id, user_id, n_type, post.id, msg)

        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def update_comment(self, comment: PostComment, user: CurrentUser, content: str) -> PostComment:
        if comment.user_id != UUID(str(user.id)):
            raise HTTPException(status_code=403, detail="Only owner can update comment")
        comment.content = content
        comment.updated_at = datetime.now(timezone.utc)
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    # 행은 남기고(대댓글 유지) 원문과 그 댓글로 생긴 알림을 지운다. 목록에는 "삭제된 댓글입니다"로 보인다
    async def delete_comment(self, comment: PostComment, user: CurrentUser) -> None:
        if comment.user_id != UUID(str(user.id)) and user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Not authorized")

        post = await self.get_or_404(comment.post_id)
        if post.instructor_id != comment.user_id:
            await self.notifications.delete_comment_notification(
                post.instructor_id, comment.user_id, post.id, self._comment_notification_message(comment.content)
            )

        comment.content = ""
        comment.deleted_at = datetime.now(timezone.utc)
        self.session.add(comment)
        await self.session.commit()

    # ── 좋아요 ────────────────────────────────────────────────────────────────

    # 좋아요 토글: 누르면 알림 생성, 취소하면 알림 없이 그 좋아요 알림도 지움 (다시 눌러도 알림이 쌓이지 않음)
    async def toggle_like(self, post: Post, user_id: UUID) -> bool:
        res = await self.session.execute(
            select(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == user_id)
        )
        existing_like = res.scalar_one_or_none()

        if existing_like:
            await self.session.delete(existing_like)
            await self.notifications.delete_like_notification(post.instructor_id, user_id, post.id)
            await self.session.commit()
            return False

        self.session.add(PostLike(post_id=post.id, user_id=user_id))
        if post.instructor_id != user_id:
            await self.notifications.create_notification(
                post.instructor_id, user_id, NotificationType.LIKE, post.id, "내 게시글을 좋아합니다."
            )
        await self.session.commit()
        return True
