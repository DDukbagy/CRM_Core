from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete, exists, and_, or_
from sqlalchemy.orm import selectinload

from app.domains.posts.models import Post, PostMedia, MediaType, Comment, PostLike, PostType, Notification, NotificationType
from app.domains.posts.schemas import PostCreate, CommentCreate, PostUpdate, CommentUpdate

class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 게시물 생성 및 저장
    async def create(self, post_in: PostCreate, created_by_user_id: UUID) -> Post:
        db_obj = Post(
            **post_in.model_dump(),
            created_by_user_id=created_by_user_id,
            owner_user_id=created_by_user_id
        )
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    # 게시물 수정 (선택적 업데이트)
    async def update(self, post_obj: Post, payload: PostUpdate) -> Post:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(post_obj, key, value)
        
        post_obj.updated_at = datetime.now(timezone.utc)
        self.session.add(post_obj)
        await self.session.commit()
        await self.session.refresh(post_obj)
        return post_obj

    # 키워드 검색 및 타입 필터링
    async def search_posts(self, keyword: str = None, post_type: PostType = None, skip: int = 0, limit: int = 50) -> List[Post]:
        query = select(Post).options(selectinload(Post.media)).where(Post.status == "PUBLIC")
        
        if keyword:
            query = query.where(
                or_(
                    Post.title.ilike(f"%{keyword}%"),
                    Post.caption.ilike(f"%{keyword}%")
                )
            )
        if post_type:
            query = query.where(Post.post_type == post_type)
            
        query = query.order_by(desc(Post.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    # 미디어 추가
    async def add_media(self, post_id: UUID, url: str, s3_key: str, media_type: MediaType) -> PostMedia:
        query = select(func.max(PostMedia.sort_order)).where(PostMedia.post_id == post_id)
        result = await self.session.execute(query)
        max_order = result.scalar()

        next_order = 0 if max_order is None else max_order + 1
        
        media = PostMedia(
            post_id=post_id,
            url=url,
            s3_key_source=s3_key,
            media_type=media_type,
            sort_order=next_order 
        )
        self.session.add(media)
        await self.session.commit()
        await self.session.refresh(media)
        return media

    # ID로 게시물 단건 조회
    async def get_by_id(self, post_id: UUID) -> Optional[Post]:
        query = select(Post).options(selectinload(Post.media)).where(Post.id == post_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
        
    # 댓글 작성 및 알림 생성
    async def create_comment(self, post_id: UUID, user_id: UUID, payload: CommentCreate) -> Comment:
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=payload.content,
            parent_id=payload.parent_id
        )
        self.session.add(comment)

        # 알림 전송 로직
        post = await self.get_by_id(post_id)
        if post and post.owner_user_id != user_id:
            n_type = NotificationType.REPLY if payload.parent_id else NotificationType.COMMENT
            msg = f"내 게시글에 댓글이 달렸습니다: {payload.content[:20]}"
            await self.create_notification(post.owner_user_id, user_id, n_type, post_id, msg)

        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    # 댓글 수정
    async def update_comment(self, comment_id: UUID, payload: CommentUpdate) -> Optional[Comment]:
        comment = await self.get_comment_by_id(comment_id)
        if comment:
            comment.content = payload.content
            comment.updated_at = datetime.now(timezone.utc)
            self.session.add(comment)
            await self.session.commit()
            await self.session.refresh(comment)
        return comment

    # 댓글 목록 조회
    async def get_comments_by_post(self, post_id: UUID, skip: int = 0, limit: int = 50) -> List[Comment]:
        query = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .order_by(desc(Comment.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    # 댓글 삭제
    async def delete_comment(self, comment_id: UUID) -> bool:
        query = delete(Comment).where(Comment.id == comment_id)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount > 0

    # 댓글 단건 조회
    async def get_comment_by_id(self, comment_id: UUID) -> Optional[Comment]:
        query = select(Comment).where(Comment.id == comment_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # 좋아요 토글 및 알림 생성
    async def toggle_like(self, post_id: UUID, user_id: UUID) -> bool:
        query = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        )
        result = await self.session.execute(query)
        existing_like = result.scalar_one_or_none()

        if existing_like:
            await self.session.delete(existing_like)
            await self.session.commit()
            return False 
        else:
            new_like = PostLike(post_id=post_id, user_id=user_id)
            self.session.add(new_like)

            # 알림 전송 로직
            post = await self.get_by_id(post_id)
            if post and post.owner_user_id != user_id:
                await self.create_notification(post.owner_user_id, user_id, NotificationType.LIKE, post_id, "내 게시글을 좋아합니다.")

            await self.session.commit()
            return True 

    # 게시물 상세 정보 및 카운트 주입
    async def get_post_with_counts(self, post_id: UUID, user_id: Optional[UUID] = None) -> Optional[Post]:
        post = await self.get_by_id(post_id)
        if not post:
            return None

        like_count = (await self.session.execute(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id))).scalar() or 0
        comment_count = (await self.session.execute(select(func.count()).select_from(Comment).where(Comment.post_id == post_id))).scalar() or 0

        is_liked = False
        if user_id:
            is_liked = (await self.session.execute(select(exists().where(and_(PostLike.post_id == post_id, PostLike.user_id == user_id))))).scalar() or False

        object.__setattr__(post, "like_count", like_count)
        object.__setattr__(post, "comment_count", comment_count)
        object.__setattr__(post, "is_liked", is_liked)
        
        return post

    # 알림 생성 (내부 메서드)
    async def create_notification(self, recipient_id: UUID, sender_id: UUID, n_type: NotificationType, post_id: UUID, content: str):
        new_notif = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=n_type,
            related_post_id=post_id,
            content=content
        )
        self.session.add(new_notif)

    # 내 알림 목록 조회
    async def get_my_notifications(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Notification]:
        query = (
            select(Notification)
            .where(Notification.recipient_id == user_id)
            .order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    # 알림 읽음 처리
    async def mark_notification_as_read(self, user_id: UUID, notification_id: UUID) -> bool:
        query = select(Notification).where(
            and_(Notification.id == notification_id, Notification.recipient_id == user_id)
        )
        res = await self.session.execute(query)
        notif = res.scalar_one_or_none()
        if notif:
            notif.is_read = True
            await self.session.commit()
            return True
        return False