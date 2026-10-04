from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DiscountType = Literal["PERCENT", "AMOUNT", "NONE"]


def _check_discount(discount_type: Optional[str], value: Optional[int]) -> None:
    if discount_type == "PERCENT" and not (value and 1 <= value <= 100):
        raise ValueError("할인율은 1~100(%) 이어야 합니다.")
    if discount_type == "AMOUNT" and not (value and value > 0):
        raise ValueError("할인 금액은 0원보다 커야 합니다.")


class PromotionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    pass_type_id: Optional[int] = None
    discount_type: DiscountType = "NONE"
    discount_value: int = Field(default=0, ge=0)
    start_date: date
    end_date: date
    is_active: bool = True
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 같거나 늦어야 합니다.")
        _check_discount(self.discount_type, self.discount_value)
        return self


class PromotionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    pass_type_id: Optional[int] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[int] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="forbid")


class PromotionRead(BaseModel):
    id: int
    instructor_id: UUID
    pass_type_id: Optional[int] = None
    pass_type_name: Optional[str] = None
    pass_price: Optional[int] = None
    discounted_price: Optional[int] = None   # 안내용 (결제 연동 전, 실제 결제에는 미적용)
    title: str
    description: Optional[str] = None
    discount_type: str
    discount_value: int
    start_date: date
    end_date: date
    is_active: bool
    status: str                              # SCHEDULED(예정) | ONGOING(진행 중) | ENDED(종료) | PAUSED(중지)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
