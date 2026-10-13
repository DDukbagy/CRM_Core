# 상태 확인 API (배포·로드밸런서 확인용)
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


# 서버 동작 확인
@router.get("")
async def health():
    return {"status": "ok"}

# 요청 받을 준비 확인
@router.get("/ready")
async def ready():
    return {"status": "ok"}

# DB 연결 확인
@router.get("/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}