from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    """
    사용자 조회 응답(외부 노출용)
    - password 같은 민감 정보는 절대 포함하지 않는다
    """
    id: UUID
    username: str
    email: EmailStr | None = None
    display_name: str
    role: str
    created_at: datetime
    updated_at: datetime

    # SQLModel/ORM 객체를 그대로 반환해도 스키마로 변환
    model_config = {"from_attributes": True}

class UsersListResponse(BaseModel):
    """
    사용자 목록 응답
    - 확장성(페이지네이션/메타데이터)을 위해 래퍼 형태로 고정
    """
    items: list[UserRead]
    total: int | None = None
    limit: int | None = None
    offset: int | None = None

class UserUpdate(BaseModel):
    """
    사용자 정보 수정 요청(부분 수정용)
    - PATCH 등에 사용
    - None은 "변경 안 함" 의미
    """
    username: str | None = None
    email: EmailStr | None = None
    display_name: str | None = None

    model_config = {"extra": "forbid"}

class UserCreateFromAuth(BaseModel):
    """
    Supabase Auth(소셜/이메일 로그인) 이후 우리 users 테이블 row를 생성/동기화할 때 쓰는 내부 스키마
    - Supabase를 쓰면 'password'는 보통 우리 백엔드가 직접 받지 않는다
    - users.id는 Supabase JWT의 sub(UUID) 값을 그대로 사용
    """
    id: UUID
    username: str
    email: EmailStr | None = None
    display_name: str
    role: str = "CUSTOMER"

    model_config = {"extra": "forbid"}
    