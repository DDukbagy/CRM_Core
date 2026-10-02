from __future__ import annotations

import asyncio
from logging.config import fileConfig
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# 경로 설정 및 .env 로딩
# ----------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
sys.path.append(str(project_root))

env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# ----------------------------------------------------------------------
# 모델 등록
# ----------------------------------------------------------------------
try:
    from app.core.config import settings

    from sqlmodel import SQLModel
    from app.db.base import Base
    # 모델 등록 목록은 app/db/models.py 한 곳에서 관리한다
    import app.db.models  # noqa: F401

    # passes, chat 은 비교 명령(check / revision --autogenerate)에서만 올린다.
    # upgrade 때 올리면 init 마이그레이션의 create_all 이 두 도메인 테이블을 먼저 만들어
    # 각자의 마이그레이션(j4k5l6m7n8o9, k5l6m7n8o9p0)이 실패한다 (app/db/models.py 주석 참고).
    _cmd_opts = getattr(context.config, "cmd_opts", None)
    _cmd_name = getattr(getattr(_cmd_opts, "cmd", (None,))[0], "__name__", "")
    if _cmd_name in ("check", "revision"):
        import app.domains.passes.models  # noqa: F401
        import app.domains.chat.models  # noqa: F401

    # 메타데이터 통합
    if hasattr(Base, "metadata") and hasattr(SQLModel, "metadata"):
        for name, table in Base.metadata.tables.items():
            if name not in SQLModel.metadata.tables:
                table.to_metadata(SQLModel.metadata)

    target_metadata = SQLModel.metadata

except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(f"🔍 Current sys.path: {sys.path}")
    raise e

# ----------------------------------------------------------------------
# DB URL 확인 — 주소는 출력하지 않는다 (호스트·계정 정보 노출 방지)
# ----------------------------------------------------------------------
if not settings.ASYNC_DATABASE_URL:
    print("❌ ERROR: settings.ASYNC_DATABASE_URL is empty!")

# ----------------------------------------------------------------------
# Alembic 설정 (Standard)
# ----------------------------------------------------------------------
config = context.config

def include_object(object_, name, type_, reflected, compare_to):
    if reflected and compare_to is None:
        return False
    return True

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    url = settings.ASYNC_DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.ASYNC_DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())

run_migrations()