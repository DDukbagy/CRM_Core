from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]  # /workspace
sys.path.insert(0, str(ROOT_DIR))

import uuid
from datetime import date, timedelta
from typing import AsyncIterator, Tuple, Optional

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.main import app
from app.db.session import get_session
from app.core.auth.deps import CurrentUser
from app.core.auth import deps as auth_deps

import app.domains.calendar.router as calendar_router


async def _ensure_test_user_id(session: AsyncSession) -> uuid.UUID:
    # 기존 users에서 하나 가져오기 (있으면 가장 안전)
    res = await session.execute(text("select id from public.users limit 1"))
    row = res.first()
    if row and row[0]:
        return uuid.UUID(str(row[0]))

    # 없으면 생성 시도 (스키마가 다르면 여기서 실패할 수 있음)
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role)
            values (:id, :username, :email, :display_name, true, 'ACTIVE', 'CUSTOMER')
            """
        ),
        {
            "id": str(user_id),
            "username": f"test-{user_id.hex[:8]}",
            "email": f"test-{user_id.hex[:8]}@example.com",
            "display_name": f"test-{user_id.hex[:8]}",
        },
    )
    await session.commit()
    return user_id


async def _pick_free_slot_and_date(session: AsyncSession, horizon_days: int = 30) -> Optional[Tuple[int, date]]:
    """
    time_slots에서 아무거나 가져와서
    - 해당 slot이 가능한 요일(weekdays)에 맞는 날짜를 찾고
    - 그 날짜에 active booking이 없는 slot/date를 고른다.
    """
    slots = await session.execute(
        text("select id, weekdays from public.time_slots order by id limit 50")
    )
    rows = slots.fetchall()
    if not rows:
        return None

    today = date.today()

    for slot_id, weekdays in rows:
        # asyncpg는 int[]를 list[int]로 주는 경우가 많음
        wd_list = weekdays or []
        if not isinstance(wd_list, list):
            continue

        for i in range(1, horizon_days + 1):
            d = today + timedelta(days=i)
            if d.weekday() not in wd_list:
                continue

            # 해당 slot/date에 active booking이 있는지 확인
            exists = await session.execute(
                text(
                    """
                    select 1
                    from public.bookings
                    where "when" = :d
                      and time_slot_id = :slot_id
                      and status <> 'CANCELLED'
                    limit 1
                    """
                ),
                {"d": d, "slot_id": int(slot_id)},
            )
            if exists.first() is None:
                return int(slot_id), d

    return None


@pytest_asyncio.fixture
async def db_conn_and_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    테스트 1개당:
    - DB 연결 1개
    - outer transaction 1개
    - 요청마다 savepoint(session.commit 안전)로 동작
    - 테스트 끝나면 outer rollback => 데이터 안 남음
    """
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_pre_ping=True)

    async with engine.connect() as conn:
        trans = await conn.begin()

        SessionLocal = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",  # 중요: endpoint가 commit해도 outer tx는 유지
        )

        try:
            yield SessionLocal
        finally:
            await trans.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """
    FastAPI dependency override:
    - get_session -> 테스트 세션
    - get_current_user -> 테스트 유저
    """
    async with db_conn_and_sessionmaker() as session:
        user_id = await _ensure_test_user_id(session)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as session:
            yield session

    async def override_get_current_user():
        return CurrentUser(
            id=str(user_id),
            email=None,
            phone=None,
            username="test-user",
            display_name="Test User",
            role="CUSTOMER",
            status="ACTIVE",
            is_active=True,
        )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[calendar_router.get_current_user] = override_get_current_user
    app.dependency_overrides[auth_deps.get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def free_slot_and_date(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> Tuple[int, date]:
    async with db_conn_and_sessionmaker() as session:
        picked = await _pick_free_slot_and_date(session)
        if picked is None:
            # host 유저 확보 (없으면 하나 생성)
            res = await session.execute(
                text("select id from public.users where role in ('INSTRUCTOR','ADMIN') limit 1")
            )
            row = res.first()
            if row and row[0]:
                host_id = str(row[0])
            else:
                host_uuid = uuid.uuid4()
                host_id = str(host_uuid)
                await session.execute(
                    text(
                        """
                        insert into public.users (id, username, email, display_name, is_active, status, role)
                        values (:id, :username, :email, :display_name, true, 'ACTIVE', 'INSTRUCTOR')
                        """
                    ),
                    {
                        "id": host_id,
                        "username": f"host-{host_uuid.hex[:8]}",
                        "email": f"host-{host_uuid.hex[:8]}@example.com",
                        "display_name": f"host-{host_uuid.hex[:8]}",
                    },
                )

            # calendar 확보 (없으면 생성) - calendars.host_id는 UNIQUE
            res = await session.execute(
                text("select id from public.calendars where host_id = :host_id limit 1"),
                {"host_id": host_id},
            )
            cal = res.first()
            if cal and cal[0]:
                calendar_id = int(cal[0])
            else:
                ins = await session.execute(
                    text("""
                        insert into public.calendars (topics, description, host_id)
                        values (CAST(:topics AS jsonb), :description, :host_id)
                        returning id
                    """),
                    {               
                        "topics": '["테스트"]',
                        "description": "테스트 캘린더",
                        "host_id": host_id,
                    },
                )
                calendar_id = int(ins.scalar_one())

            # time_slot 이미 있으면 재사용, 없으면 생성
            res = await session.execute(
                text("""
                    select id
                    from public.time_slots
                    where calendar_id = :calendar_id
                      and start_time = '09:00'::time
                      and end_time = '10:00'::time
                    limit 1
                """),
                {"calendar_id": calendar_id},
            )
            slot_row = res.first()

            if not (slot_row and slot_row[0]):
                await session.execute(
                    text("""
                        insert into public.time_slots (start_time, end_time, weekdays, is_active, calendar_id)
                        values ('09:00'::time, '10:00'::time, '[0,1,2,3,4,5,6]'::jsonb, true, :calendar_id)
                    """),
                    {"calendar_id": calendar_id},
                )

            await session.commit()

            # 다시 pick
            picked = await _pick_free_slot_and_date(session)
            if picked is None:
                raise AssertionError(
                    "free_slot_and_date: seed 이후에도 30일 내 예약 가능한 slot/date를 찾지 못했습니다."
                )

        return picked


# ── Instructor / Customer helpers ─────────────────────────────

async def _ensure_instructor(session: AsyncSession, tier: str = "NORMAL") -> uuid.UUID:
    instructor_uuid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users (id, username, email, display_name, is_active, status, role, instructor_tier)
            VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'INSTRUCTOR', :tier)
            """
        ),
        {
            "id": str(instructor_uuid),
            "username": f"instr-{instructor_uuid.hex[:8]}",
            "email": f"instr-{instructor_uuid.hex[:8]}@example.com",
            "display_name": "Test Instructor",
            "tier": tier,
        },
    )
    await session.commit()
    return instructor_uuid


async def _ensure_customer_managed_by(session: AsyncSession, manager_id: uuid.UUID) -> uuid.UUID:
    customer_uuid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users (id, username, email, display_name, is_active, status, role, manager_id)
            VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'CUSTOMER', :manager_id)
            """
        ),
        {
            "id": str(customer_uuid),
            "username": f"cust-{customer_uuid.hex[:8]}",
            "email": f"cust-{customer_uuid.hex[:8]}@example.com",
            "display_name": "Test Customer",
            "manager_id": str(manager_id),
        },
    )
    await session.commit()
    return customer_uuid


@pytest_asyncio.fixture
async def instructor_id(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with db_conn_and_sessionmaker() as session:
        return await _ensure_instructor(session)


@pytest_asyncio.fixture
async def named_instructor_id(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with db_conn_and_sessionmaker() as session:
        return await _ensure_instructor(session, tier="NAMED")


@pytest_asyncio.fixture
async def managed_customer_id(
    db_conn_and_sessionmaker: async_sessionmaker[AsyncSession],
    instructor_id: uuid.UUID,
) -> uuid.UUID:
    async with db_conn_and_sessionmaker() as session:
        return await _ensure_customer_managed_by(session, instructor_id)


@pytest_asyncio.fixture
async def instructor_client(
    db_conn_and_sessionmaker: async_sessionmaker[AsyncSession],
    instructor_id: uuid.UUID,
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as session:
            yield session

    async def override_get_current_user():
        return CurrentUser(
            id=str(instructor_id),
            email=None,
            phone=None,
            username="test-instructor",
            display_name="Test Instructor",
            role="INSTRUCTOR",
            status="ACTIVE",
            is_active=True,
        )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[calendar_router.get_current_user] = override_get_current_user
    app.dependency_overrides[auth_deps.get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
