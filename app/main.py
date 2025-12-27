from __future__ import annotations

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_session

from app.domains.account.router import router as account_router
from app.domains.calendar.router import router as calendar_router

app = FastAPI()

# CORS (운영에서는 허용 도메인만 넣는 방식으로 좁히는 게 정석)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # 예: ["http://localhost:3000", "http://localhost:8000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    result = await session.execute(text("SELECT 1"))
    return {"ok"}


app.include_router(account_router)
app.include_router(calendar_router)
