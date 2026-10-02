# `from __future__ import annotations`를 쓰지 않는다. @limiter.limit 래퍼 때문에 FastAPI가
# 문자열 타입을 풀지 못할 수 있다(payment/router.py 결제 등록 422와 같은 원인).
from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser, get_current_user
from app.db.session import get_session
from app.domains.auth.repository import AuthRepository

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


# 아이디/비밀번호 로그인 → 백엔드가 직접 서명한 HS256 토큰 발급 (Supabase 로그인의 폴백, 웹 api/dev-login 이 사용)
@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(OAuth2PasswordRequestForm),
    session: AsyncSession = Depends(get_session),
):
    """[로그인] 아이디/비밀번호를 확인하고 JWT 토큰을 발급합니다."""
    return await AuthRepository(session).login(form_data.username, form_data.password)
