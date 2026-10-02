from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, verify_password
from app.domains.users.models import User


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def login(self, username: str, password: str) -> dict:
        """아이디/비밀번호 확인 후 백엔드 HS256 토큰 발급 (Supabase 로그인의 폴백)

        아이디가 없거나 비밀번호가 틀리면 같은 메시지로 400 (어느 쪽인지 알려주지 않는다).
        """
        user = (await self.session.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not user or not verify_password(password, user.password):
            raise HTTPException(status_code=400, detail="아이디 또는 비밀번호가 틀렸습니다.")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="비활성화된 계정입니다.")

        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user.role,                 # 프론트엔드가 화면을 고르기 위해 필요
            "display_name": user.display_name,  # 환영 인사용
        }
