from datetime import datetime, timezone, date
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID

from pydantic import EmailStr, AwareDatetime
from sqlalchemy import UniqueConstraint, String, Text, SmallInteger, Date
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field, Relationship, func
from sqlalchemy_utc import UtcDateTime

# 순환 참조 방지
if TYPE_CHECKING:
    from app.domains.calendar.models import Calendar, Booking


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_email"),
    )

    id: UUID = Field(primary_key=True, sa_type=PGUUID(as_uuid=True))

    username: str = Field(unique=True, max_length=40, description="사용자 계정 ID")

    email: Optional[EmailStr] = Field(
        default=None,
        sa_type=String(255),
        index=True,
        unique=True,
        nullable=True,
        description="사용자 이메일",
    )

    display_name: str = Field(max_length=40, description="사용자 표시 이름")

    phone: Optional[str] = Field(default=None, max_length=20, description="전화번호")

    role: str = Field(
        sa_type=String(20),
        nullable=False,
        description="사용자 역할 (CUSTOMER, INSTRUCTOR, CONTENT_MANAGER, ADMIN)",
    )

    # ✅승인/상태
    status: str = Field(
        default="ACTIVE",
        sa_type=String(20),
        nullable=False,
        description="계정 상태 (ACTIVE, PENDING, SUSPENDED)",
    )

    manager_id: Optional[UUID] = Field(
        default=None,
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        description="담당 강사/관리자 ID"
    )

    instructor_tier: Optional[str] = Field(
        default="NORMAL",
        sa_type=String(10),
        nullable=True,
        description="강사 등급: NORMAL(무료 매칭) | NAMED(유료 매칭)",
    )

    instructor_location: Optional[str] = Field(
        default=None,
        sa_type=String(50),
        nullable=True,
        description="강사 활동 지역",
    )

    instructor_specialties: Optional[str] = Field(
        default=None,
        sa_type=String(255),
        nullable=True,
        description="레슨 스타일/전문 분야 (콤마 구분)",
    )

    instructor_bio: Optional[str] = Field(
        default=None,
        sa_type=Text,
        nullable=True,
        description="강사 소개글",
    )

    # ── 강사 추가 정보 ────────────────────────────
    career_years: Optional[int] = Field(
        default=None,
        sa_type=SmallInteger,
        nullable=True,
        description="강사 경력 연수",
    )

    certifications: Optional[str] = Field(
        default=None,
        sa_type=Text,
        nullable=True,
        description="강사 자격증 (콤마 구분)",
    )

    # ── 고객 추가 정보 ────────────────────────────
    birth_date: Optional[date] = Field(
        default=None,
        sa_type=Date,
        nullable=True,
        description="고객 생년월일",
    )

    gender: Optional[str] = Field(
        default=None,
        sa_type=String(10),
        nullable=True,
        description="성별 (MALE / FEMALE / OTHER)",
    )

    lesson_purpose: Optional[str] = Field(
        default=None,
        sa_type=Text,
        nullable=True,
        description="레슨 목적/목표",
    )

    is_active: bool = Field(
        default=True,
        nullable=False,
        description="계정 활성화 여부"
    )

    password: Optional[str] = Field(default=None, max_length=128, description="사용자 비밀번호")

    created_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )

    updated_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )

    # Relationships
    oauth_accounts: List["OAuthAccount"] = Relationship(back_populates="user")

    calendar: Optional["Calendar"] = Relationship(
        back_populates="host",
        sa_relationship_kwargs={"uselist": False, "single_parent": True},
    )

    bookings: List["Booking"] = Relationship(back_populates="guest")


class OAuthAccount(SQLModel, table=True):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_account_id",
            name="uq_provider_provider_account_id",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    provider: str = Field(max_length=10, description="OAuth 제공자")
    provider_account_id: str = Field(max_length=128, description="OAuth 제공자 계정 ID")

    user_id: UUID = Field(foreign_key="users.id", sa_type=PGUUID(as_uuid=True))

    user: "User" = Relationship(back_populates="oauth_accounts")

    created_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )

    updated_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )