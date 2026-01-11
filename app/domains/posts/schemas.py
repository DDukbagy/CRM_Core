from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class PostCreateAdmin(BaseModel):
    owner_user_id: UUID
    caption: str | None = None
    # 강사/스태프가 만든 post면 스코프 고정용으로 채우는 걸 추천
    instructor_id: UUID | None = None

    model_config = {"extra": "forbid"}


class PostRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    created_by_user_id: UUID | None
    instructor_id: UUID | None
    caption: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}
