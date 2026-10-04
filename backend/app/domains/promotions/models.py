from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel, func


class Promotion(SQLModel, table=True):
    """
    강사의 할인·이벤트 프로모션 (프로토타입, 2026-10-04)
    - 강사 웹에서 만들고 수정, 강사 앱은 확인만, 고객 앱 수강권 탭에 표시
    - 결제 연동 전이라 실제 가격 할인은 적용하지 않고 안내만 한다
    - pass_type_id 를 지정하면 그 수강권 상품의 할인 (없으면 강사 전체 이벤트)

    lesson_pass_types 를 참조하므로 passes 처럼 app/db/models.py 에 등록하지 않는다
    (init 마이그레이션의 create_all 시점에는 lesson_pass_types 가 없음). 테이블은 y0z1a2b3c4d5 가 만든다.
    """
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("discount_type IN ('PERCENT', 'AMOUNT', 'NONE')", name="ck_promotions_discount_type"),
        CheckConstraint("end_date >= start_date", name="ck_promotions_period"),
    )

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    instructor_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    pass_type_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("lesson_pass_types.id", ondelete="SET NULL"), nullable=True),
    )
    title: str = Field(sa_column=Column(String(100), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    # PERCENT: discount_value % / AMOUNT: discount_value 원 / NONE: 할인 없는 이벤트 안내
    discount_type: str = Field(default="NONE", sa_column=Column(String(10), nullable=False, server_default="NONE"))
    discount_value: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    start_date: date = Field(sa_column=Column(Date, nullable=False))
    end_date: date = Field(sa_column=Column(Date, nullable=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
    )
