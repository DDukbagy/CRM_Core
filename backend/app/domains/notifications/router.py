from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser, get_current_user
from app.db.session import get_session
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# 내 알림 목록 조회
@router.get("", response_model=List[NotificationResponse])
async def list_my_notifications(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    repo = NotificationRepository(session)
    notifications = await repo.get_my_notifications(UUID(str(user.id)), skip, limit)
    return notifications

# 알림 읽음 처리
@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    repo = NotificationRepository(session)
    success = await repo.mark_notification_as_read(UUID(str(user.id)), notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found or access denied")
    return {"ok": True}
