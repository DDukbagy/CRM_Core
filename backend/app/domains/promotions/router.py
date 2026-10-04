from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.domains.promotions.repository import PromotionRepository
from app.domains.promotions.schemas import PromotionCreate, PromotionRead, PromotionUpdate

router = APIRouter(prefix="/promotions", tags=["Promotion"])
INSTRUCTOR = {"INSTRUCTOR"}


@router.get("/me", response_model=list[PromotionRead])
async def list_my_promotions(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(INSTRUCTOR)),
):
    """강사: 내 프로모션 전체 (예정·진행 중·종료·중지)"""
    repo = PromotionRepository(session)
    return [await repo.to_read(p) for p in await repo.list_mine(UUID(str(user.id)))]


@router.post("", response_model=PromotionRead, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    data: PromotionCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(INSTRUCTOR)),
):
    repo = PromotionRepository(session)
    return await repo.to_read(await repo.create(UUID(str(user.id)), data))


@router.patch("/{promotion_id}", response_model=PromotionRead)
async def update_promotion(
    promotion_id: int,
    data: PromotionUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(INSTRUCTOR)),
):
    repo = PromotionRepository(session)
    return await repo.to_read(await repo.update(promotion_id, UUID(str(user.id)), data))


@router.delete("/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promotion(
    promotion_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(INSTRUCTOR)),
):
    await PromotionRepository(session).delete(promotion_id, UUID(str(user.id)))
    return None


@router.get("/instructor/{instructor_id}", response_model=list[PromotionRead])
async def list_ongoing_promotions(
    instructor_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객 수강권 탭: 그 강사의 진행 중인 프로모션"""
    repo = PromotionRepository(session)
    return [await repo.to_read(p) for p in await repo.list_ongoing(instructor_id)]
