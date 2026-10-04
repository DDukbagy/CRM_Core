from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.domains.passes.models import LessonPassType
from app.domains.promotions.models import Promotion
from app.domains.promotions.schemas import PromotionCreate, PromotionRead, PromotionUpdate, _check_discount


def promotion_status(p: Promotion, today: Optional[date] = None) -> str:
    today = today or date.today()
    if not p.is_active:
        return "PAUSED"
    if today < p.start_date:
        return "SCHEDULED"
    if today > p.end_date:
        return "ENDED"
    return "ONGOING"


def discounted(price: Optional[int], discount_type: str, value: int) -> Optional[int]:
    if price is None or discount_type == "NONE":
        return None
    if discount_type == "PERCENT":
        return max(0, round(price * (100 - value) / 100))
    return max(0, price - value)


class PromotionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def to_read(self, p: Promotion) -> PromotionRead:
        pt = await self.session.get(LessonPassType, p.pass_type_id) if p.pass_type_id else None
        read = PromotionRead(
            **{k: getattr(p, k) for k in (
                "id", "instructor_id", "pass_type_id", "title", "description", "discount_type", "discount_value",
                "start_date", "end_date", "is_active", "created_at", "updated_at",
            )},
            status=promotion_status(p),
        )
        if pt:
            read.pass_type_name = pt.name
            read.pass_price = pt.price
            read.discounted_price = discounted(pt.price, p.discount_type, p.discount_value)
        return read

    async def list_mine(self, instructor_id: UUID) -> list[Promotion]:
        res = await self.session.execute(
            select(Promotion).where(Promotion.instructor_id == instructor_id).order_by(Promotion.start_date.desc(), Promotion.id.desc())
        )
        return list(res.scalars().all())

    async def list_ongoing(self, instructor_id: UUID) -> list[Promotion]:
        """고객에게 보이는 것: 켜져 있고 오늘이 기간 안"""
        today = date.today()
        res = await self.session.execute(
            select(Promotion)
            .where(
                Promotion.instructor_id == instructor_id,
                Promotion.is_active == True,  # noqa: E712
                Promotion.start_date <= today,
                Promotion.end_date >= today,
            )
            .order_by(Promotion.end_date.asc())
        )
        return list(res.scalars().all())

    async def _get_own(self, promotion_id: int, instructor_id: UUID) -> Promotion:
        p = await self.session.get(Promotion, promotion_id)
        if not p or p.instructor_id != instructor_id:
            raise HTTPException(status_code=404, detail="프로모션을 찾을 수 없습니다.")
        return p

    async def _check_pass_type(self, pass_type_id: Optional[int], instructor_id: UUID) -> None:
        if pass_type_id is None:
            return
        pt = await self.session.get(LessonPassType, pass_type_id)
        if not pt or pt.instructor_id != instructor_id:
            raise HTTPException(status_code=404, detail="수강권 상품을 찾을 수 없습니다.")

    async def create(self, instructor_id: UUID, data: PromotionCreate) -> Promotion:
        await self._check_pass_type(data.pass_type_id, instructor_id)
        p = Promotion(instructor_id=instructor_id, **data.model_dump())
        if p.discount_type == "NONE":
            p.discount_value = 0
        self.session.add(p)
        await self.session.commit()
        await self.session.refresh(p)
        return p

    async def update(self, promotion_id: int, instructor_id: UUID, data: PromotionUpdate) -> Promotion:
        p = await self._get_own(promotion_id, instructor_id)
        changes = data.model_dump(exclude_unset=True)
        if "pass_type_id" in changes:
            await self._check_pass_type(changes["pass_type_id"], instructor_id)
        for k, v in changes.items():
            setattr(p, k, v)
        if p.end_date < p.start_date:
            raise HTTPException(status_code=422, detail="종료일은 시작일보다 같거나 늦어야 합니다.")
        try:
            _check_discount(p.discount_type, p.discount_value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if p.discount_type == "NONE":
            p.discount_value = 0
        self.session.add(p)
        await self.session.commit()
        await self.session.refresh(p)
        return p

    async def delete(self, promotion_id: int, instructor_id: UUID) -> None:
        p = await self._get_own(promotion_id, instructor_id)
        await self.session.delete(p)
        await self.session.commit()
