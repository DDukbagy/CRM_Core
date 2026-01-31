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
# 1. 경로 설정 및 .env 로딩
# ----------------------------------------------------------------------
current_file = Path(__file__).resolve()
project_root = current_file.parents[1]
sys.path.append(str(project_root))

env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# ----------------------------------------------------------------------
# 2. 모델 등록 (가장 중요!)
# ----------------------------------------------------------------------
try:
    from app.core.config import settings
    
    # [수정됨] 라이브러리에서 직접 SQLModel 가져오기
    from sqlmodel import SQLModel
    
    # [핵심] 우리가 만든 모델 파일들을 여기서 import 해줘야 Alembic이 인식합니다.
    # 여기에 User 등 다른 모델이 있다면 추가해야 합니다.
    from app.domains.posts.models import Post 
    # from app.domains.users.models import User  <-- (예시: 유저 모델이 있다면 주석 해제)

    # 모든 모델이 로드된 후 metadata 연결
    target_metadata = SQLModel.metadata

except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(f"🔍 Current sys.path: {sys.path}")
    raise e

# ----------------------------------------------------------------------
# 3. DB URL 확인 (디버깅)
# ----------------------------------------------------------------------
db_url = settings.ASYNC_DATABASE_URL
if db_url:
    masked_url = str(db_url).replace(str(db_url).split(":")[2].split("@")[0], "****") if "@" in str(db_url) else db_url
    print(f"✅ Alembic is using DB URL: {masked_url}")
else:
    print("❌ ERROR: settings.ASYNC_DATABASE_URL is empty!")

# ----------------------------------------------------------------------
# 4. Alembic 설정 (Standard)
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