from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domains.account.router import router as account_router

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    result = await session.execute(text("SELECT 1"))
    value = result.scalar_one()
    return {"db": value}


app.include_router(account_router)
