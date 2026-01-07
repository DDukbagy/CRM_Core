from __future__ import annotations

import os
import ssl, certifi
from typing import AsyncGenerator

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.engine.url import make_url

from app.core.config import settings

connect_args = {}

SUPABASE_CA = Path(__file__).resolve().parent.parent / "certs" / "prod-ca-2021.crt"

if not SUPABASE_CA.exists():
    raise FileNotFoundError(f"Supabase CA not found: {SUPABASE_CA}")

ssl_ctx = ssl.create_default_context(cafile=certifi.where())
ssl_ctx.load_verify_locations(cafile=str(SUPABASE_CA))

if os.getenv("DB_SSL_DISABLE") == "1" or "@crm-pg:" in settings.DATABASE_URL:
    connect_args["ssl"] = None

def get_async_db_url() -> str:
    async_url = getattr(settings, "ASYNC_DATABASE_URL", None)
    if async_url:
        return async_url

    db_url = getattr(settings, "DATABASE_URL", None)
    if not db_url:
        raise RuntimeError("DATABASE_URL 또는 ASYNC_DATABASE_URL이 필요합니다.")

    # DATABASE_URL(postgresql://...) -> postgresql+asyncpg://... 로 변환
    return str(make_url(db_url).set(drivername="postgresql+asyncpg"))

def make_engine():
    ssl_ctx = ssl.create_default_context()

    common = dict(
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args={"ssl": ssl_ctx, "statement_cache_size": 0},
    )

    db_url = get_async_db_url()
    url = make_url(db_url)

    is_pooler = (url.port == 6543) or ("pooler" in (url.host or ""))

    if is_pooler:
        return create_async_engine(
            db_url,
            poolclass=NullPool,
            **common,
        )

    return create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        **common,
    )

engine = make_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
