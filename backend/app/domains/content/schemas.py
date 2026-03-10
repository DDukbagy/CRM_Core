from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class PostCreate(BaseModel):
    type: str  # PROMOTION | FEEDBACK
    title: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    customer_id: Optional[UUID] = None  # required for FEEDBACK
    is_public: bool = False
    model_config = ConfigDict(extra="forbid")


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    is_public: Optional[bool] = None
    model_config = ConfigDict(extra="forbid")


class PostRead(BaseModel):
    id: UUID
    instructor_id: UUID
    type: str
    title: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    customer_id: Optional[UUID] = None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
