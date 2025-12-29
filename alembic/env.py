from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.db.models  # noqa: F401
from app.db.base import Base


# alembic.ini 읽기
config = context.config

target_metadata = Base.metadata

def include_object(object_, name, type_, reflected, compare_to):
    # DB에만 존재(reflected=True)하고, 코드(metadata)에는 없는(compare_to is None) 객체는 제외
    # => autogenerate가 drop_table/drop_column 같은 파괴적 변경을 만들지 못하게 막음
    if reflected and compare_to is None:
        return False
    return True

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# app import 되게 경로 추가 (레포 루트)
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from app.core.config import settings  # noqa: E402

# ✅ 여기 target_metadata를 네 ORM 메타데이터로 연결해야 autogenerate 가능
# 1) SQLAlchemy Declarative Base를 쓰면: from app.db.base import Base; target_metadata = Base.metadata
# 2) SQLModel을 쓰면: from sqlmodel import SQLModel; target_metadata = SQLModel.metadata
# ---- 너 프로젝트에 맞는 걸로 "하나만" 선택 ----

try:
    # 예시: SQLAlchemy Base를 쓰는 경우
    from app.db.base import Base  # noqa: E402
    target_metadata = Base.metadata
except Exception:
    target_metadata = None  # autogenerate 안 쓸 거면 None도 가능


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
