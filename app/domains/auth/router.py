from __future__ import annotations

from fastapi import APIRouter, Depends
from app.core.auth.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "username": user.username,
        "display_name": user.display_name,
        "is_host": user.is_host,
    }
