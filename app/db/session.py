from __future__ import annotations

import os
import ssl, certifi
from typing import AsyncGenerator

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.engine.url import make_url

from app.core.config import settings


def get_async_db_url() -> str:
    # ASYNC_DATABASE_URL이 있으면 그대로 사용
    async_url = getattr(settings, "ASYNC_DATABASE_URL", None)
    if async_url:
        return async_url

    db_url = getattr(settings, "DATABASE_URL", None)
    if not db_url:
        raise RuntimeError("DATABASE_URL 또는 ASYNC_DATABASE_URL이 필요합니다.")

    # postgresql:// -> postgresql+asyncpg:// 로 변환 (이미 asyncpg면 그대로)
    url = make_url(db_url)
    if url.drivername != "postgresql+asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return str(url)


def build_ssl_context():
    """
    기본: SSL 검증 ON
    DB_SSL_DISABLE=1 이면 ssl=None 으로 강제 비활성화 (운영에서는 비권장)
    DB_SSL_CA_PATH 가 있고 파일이 존재하면 추가 로드
    """
    if os.getenv("DB_SSL_DISABLE") == "1":
        return None

    ctx = ssl.create_default_context(cafile=certifi.where())

    ca_path = os.getenv("DB_SSL_CA_PATH")
    if ca_path and os.path.exists(ca_path):
        ctx.load_verify_locations(cafile=ca_path)

    return ctx


def make_engine():
    db_url = get_async_db_url()
    url = make_url(db_url)

    # pooler 판별 (Supabase pooler는 보통 6543 / host에 pooler 포함)
    is_pooler = (url.port == 6543) or ("pooler" in (url.host or ""))

    ssl_ctx = build_ssl_context()

    connect_args = {}
    if ssl_ctx is None:
        connect_args["ssl"] = None
    else:
        connect_args["ssl"] = ssl_ctx

    # pgbouncer(pooler)면 statement cache 끄는 게 안전
    if is_pooler:
        connect_args["statement_cache_size"] = 0

    common = dict(
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if is_pooler:
        return create_async_engine(db_url, poolclass=NullPool, **common)

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