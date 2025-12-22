from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db import get_session
from app.domains.account.models import User

router = APIRouter(
    prefix="/accounts",
    tags=["Account"],
)

@router.get("/{user_id}")
async def get_account(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
