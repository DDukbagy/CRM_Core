from __future__ import annotations

import ssl, certifi
from typing import AsyncGenerator

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

SUPABASE_CA = Path(__file__).resolve().parent.parent / "certs" / "prod-ca-2021.crt"

if not SUPABASE_CA.exists():
    raise FileNotFoundError(f"Supabase CA not found: {SUPABASE_CA}")

ssl_ctx = ssl.create_default_context(cafile=certifi.where())
ssl_ctx.load_verify_locations(cafile=str(SUPABASE_CA))

engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args={
        "ssl": ssl_ctx,
        "statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
