from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, String, Integer, SmallInteger, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field, func


class LessonPassType(SQLModel, table=True):
    """
    강사가 제공하는 수강권 상품 정의
    - 강사 1명이 여러 타입의 수강권을 등록 가능
    - 고객에게 발급(CustomerPass)될 때 스냅샷을 남겨 이후 수정 영향 차단
    """
    __tablename__ = "lesson_pass_types"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    instructor_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
    )
    name: str = Field(sa_type=String(100), nullable=False)
    duration_hours: int = Field(
        sa_column=Column(SmallInteger, nullable=False),
        description="회당 레슨 시간(시간 단위)",
    )
    session_count: int = Field(
        sa_column=Column(SmallInteger, nullable=False),
        description="총 수강 횟수",
    )
    price: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="가격(원), null=미설정",
    )
    description: Optional[str] = Field(
        default=None,
        sa_type=Text,
        nullable=True,
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )


class CustomerPass(SQLModel, table=True):
    """
    고객에게 발급된 수강권 인스턴스
    - pass_type_id로 원본 타입 참조
    - pass_name/duration_hours/sessions_total은 발급 시점 스냅샷 (타입 변경 불영향)
    - sessions_used: 누적 사용 횟수 (강사가 수업 완료 시 증가)
    - status: ACTIVE → COMPLETED(자동) / EXPIRED / CANCELLED
    """
    __tablename__ = "customer_passes"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    pass_type_id: int = Field(
        foreign_key="lesson_pass_types.id",
        nullable=False,
    )
    customer_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
    )
    instructor_id: UUID = Field(
        sa_type=PGUUID(as_uuid=True),
        foreign_key="users.id",
        nullable=False,
        description="비정규화: 빠른 강사별 조회를 위해 중복 저장",
    )

    # ── 발급 시점 스냅샷 ─────────────────────────────────────────────────────
    pass_name: str = Field(sa_type=String(100), nullable=False)
    duration_hours: int = Field(sa_column=Column(SmallInteger, nullable=False))
    sessions_total: int = Field(sa_column=Column(SmallInteger, nullable=False))

    sessions_used: int = Field(
        default=0,
        sa_column=Column(SmallInteger, nullable=False, server_default="0"),
    )
    price_paid: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="실제 결제 금액(원). null=무료/미기록",
    )
    status: str = Field(
        default="ACTIVE",
        sa_column=Column(String(20), nullable=False, server_default="ACTIVE"),
        description="ACTIVE | COMPLETED | EXPIRED | CANCELLED",
    )
    note: Optional[str] = Field(default=None, sa_type=Text, nullable=True)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
    )
