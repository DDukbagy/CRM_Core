from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from app.domains.notifications.models import NotificationType

# 알림 응답
class NotificationResponse(BaseModel):
    id: UUID
    recipient_id: UUID
    sender_id: Optional[UUID]
    notification_type: NotificationType
    related_post_id: Optional[UUID]
    content: Optional[str]
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
