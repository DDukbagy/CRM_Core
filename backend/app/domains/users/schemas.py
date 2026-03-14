from __future__ import annotations

from datetime import datetime, date
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class UserRead(BaseModel):
    """
    사용자 조회 응답(외부 노출용)
    - password 같은 민감 정보는 절대 포함하지 않는다
    """
    id: UUID
    username: str
    email: EmailStr | None = None
    display_name: str
    phone: str | None = None
    role: str

    # status
    status: str = "ACTIVE"

    manager_id: UUID | None = None

    # 강사 전용 필드
    instructor_tier: str | None = None
    instructor_location: str | None = None
    instructor_specialties: str | None = None
    instructor_bio: str | None = None
    career_years: int | None = None
    certifications: str | None = None

    # 고객 전용 필드
    birth_date: date | None = None
    gender: str | None = None
    lesson_purpose: str | None = None

    feedback_consent: bool = False
    recurring_off_days: list[int] = []

    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsersListResponse(BaseModel):
    """
    사용자 목록 응답
    - 확장성(페이지네이션/메타데이터)을 위해 래퍼 형태로 고정
    """
    items: List[UserRead]
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
    phone: str | None = None

    # 강사 프로필 필드 (INSTRUCTOR 역할에서만 의미 있음)
    instructor_location: str | None = None
    instructor_specialties: str | None = None
    instructor_bio: str | None = None
    career_years: int | None = None
    certifications: str | None = None

    # 고객 프로필 필드
    birth_date: date | None = None
    gender: str | None = None
    lesson_purpose: str | None = None
    feedback_consent: bool | None = None
    recurring_off_days: list[int] | None = None

    model_config = ConfigDict(extra="forbid")


class UserCreateFromAuth(BaseModel):
    """
    Supabase Auth 이후 우리 users 테이블 row를 생성/동기화할 때 쓰는 내부 스키마
    - users.id는 Supabase JWT의 sub(UUID) 값을 그대로 사용
    """
    id: UUID
    username: str
    email: EmailStr | None = None
    display_name: str
    role: str = "CUSTOMER"
    status: str = "ACTIVE"

    model_config = ConfigDict(extra="forbid")


class UserCreate(BaseModel):
    """
    신규 회원 등록 요청 스키마
    - (현재 Supabase Auth를 쓰면, 이 경로는 보조/테스트용일 가능성 높음)
    """
    username: str
    email: EmailStr
    display_name: str
    phone: str | None = None
    password: str
    role: str = "CUSTOMER"
    status: str = "ACTIVE"
    manager_id: UUID | None = None