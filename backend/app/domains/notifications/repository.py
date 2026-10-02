from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, delete

from app.domains.notifications.models import Notification, NotificationType

class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 알림 생성 (commit은 호출한 쪽의 트랜잭션에서 수행)
    async def create_notification(self, recipient_id: UUID, sender_id: UUID, n_type: NotificationType, post_id: UUID, content: str):
        new_notif = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=n_type,
            related_post_id=post_id,
            content=content
        )
        self.session.add(new_notif)

    # 게시물 삭제 시 그 게시물을 가리키는 알림 삭제 (commit은 호출한 쪽에서)
    async def delete_for_post(self, post_id: UUID) -> None:
        await self.session.execute(delete(Notification).where(Notification.related_post_id == post_id))

    # 댓글 삭제 시 그 댓글로 생긴 알림 1건 삭제 (알림 미리보기에 원문 일부가 들어 있으므로)
    async def delete_comment_notification(
        self, recipient_id: UUID, sender_id: UUID, post_id: UUID, content: str
    ) -> None:
        target = await self.session.execute(
            select(Notification.id)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.sender_id == sender_id,
                Notification.related_post_id == post_id,
                Notification.notification_type.in_([NotificationType.COMMENT, NotificationType.REPLY]),
                Notification.content == content,
            )
            .order_by(desc(Notification.created_at))
            .limit(1)
        )
        notification_id = target.scalar_one_or_none()
        if notification_id is not None:
            await self.session.execute(delete(Notification).where(Notification.id == notification_id))

    # 좋아요 취소 시 그 좋아요로 생긴 알림 삭제 (commit은 호출한 쪽에서)
    async def delete_like_notification(self, recipient_id: UUID, sender_id: UUID, post_id: UUID) -> None:
        await self.session.execute(
            delete(Notification).where(
                Notification.recipient_id == recipient_id,
                Notification.sender_id == sender_id,
                Notification.related_post_id == post_id,
                Notification.notification_type == NotificationType.LIKE,
            )
        )

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
