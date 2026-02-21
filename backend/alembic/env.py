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
    import app.db.models

    # 모델 import

    # [Users]
    from app.domains.users.models import User

    # [Calendar]
    from app.domains.calendar.models import Calendar, TimeSlot

    # from app.domains.posts.models import ...
    # from app.domains.booking.models import ...
    # from app.domains.match.models import ...

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
# DB URL 확인 (디버깅)
# ----------------------------------------------------------------------
db_url = settings.ASYNC_DATABASE_URL
if db_url:
    masked_url = str(db_url).replace(str(db_url).split(":")[2].split("@")[0], "****") if "@" in str(db_url) else db_url
    print(f"✅ Alembic is using DB URL: {masked_url}")
else:
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