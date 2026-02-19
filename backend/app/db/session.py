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

    connect_args = {}

    # SSL 검증 ON (Supabase CA로 검증)
    # 로컬 테스트에서만 끄고 싶으면 DB_SSL_DISABLE=1 로 실행
    if os.getenv("DB_SSL_DISABLE") == "1":
        connect_args["ssl"] = None
    else:
        SUPABASE_CA = Path(__file__).resolve().parent.parent / "certs" / "prod-ca-2021.crt"
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        ssl_ctx.load_verify_locations(cafile=str(SUPABASE_CA))
        connect_args["ssl"] = ssl_ctx

    return create_async_engine(
        db_url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args,
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