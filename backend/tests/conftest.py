# 테스트 공용 설정: 로컬 DB, 앱 클라이언트, 사용자·토큰 만들기
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]  # /workspace
sys.path.insert(0, str(ROOT_DIR))

import uuid
from datetime import date, timedelta
from typing import AsyncIterator, Optional

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.clock import today_kst
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
            insert into public.users (id, username, email, display_name, is_active, status, role, feedback_consent)
            values (:id, :username, :email, :display_name, true, 'ACTIVE', 'CUSTOMER', true)
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


# 수강권 만들기: 진행 중 레슨 예약은 수강권이 고정돼 있어야 한다 (DB 제약 ck_bookings_active_lesson_has_pass)

async def insert_customer_pass(session: AsyncSession, customer_id, instructor_id, total: int = 10) -> int:
    """고객에게 그 강사의 활성 수강권을 하나 만들고 id 를 돌려준다 (commit 함)"""
    type_id = (await session.execute(
        text("insert into public.lesson_pass_types (instructor_id, name, duration_hours, session_count, is_active)"
             " values (:i, '테스트 수강권', 1, :n, true) returning id"),
        {"i": str(instructor_id), "n": total},
    )).scalar_one()
    cp_id = (await session.execute(
        text("insert into public.customer_passes (pass_type_id, customer_id, instructor_id, pass_name, duration_hours, sessions_total)"
             " values (:t, :c, :i, '테스트 수강권', 1, :n) returning id"),
        {"t": type_id, "c": str(customer_id), "i": str(instructor_id), "n": total},
    )).scalar_one()
    await session.commit()
    return cp_id


async def insert_pass_for_slot(session: AsyncSession, customer_id, slot_id: int, total: int = 10) -> int:
    """그 슬롯의 캘린더 주인(강사) 수강권을 고객에게 만든다"""
    host = (await session.execute(
        text("select c.host_id from public.time_slots ts join public.calendars c on c.id = ts.calendar_id where ts.id = :s"),
        {"s": slot_id},
    )).scalar_one()
    return await insert_customer_pass(session, customer_id, host, total)


async def insert_booking(session: AsyncSession, *, when, status: str, slot_id: int, guest_id, customer_pass_id=None) -> int:
    """API 를 거치지 않고 예약 1건(슬롯 1개)을 바로 넣고 id 를 돌려준다 (commit 은 호출한 쪽에서)

    예약은 bookings 한 행 + 그 예약이 차지하는 시간 booking_slots 한 행이다. 취소된 예약은 시간을 차지하지 않는다.
    """
    booking_id = (await session.execute(
        text(
            'insert into public.bookings ("when", topic, type, status, calendar_id, guest_id, customer_pass_id)'
            " select :d, '레슨', 'LESSON', :st, ts.calendar_id, :g, :cp from public.time_slots ts where ts.id = :s returning id"
        ),
        {"d": when, "st": status, "s": slot_id, "g": str(guest_id), "cp": customer_pass_id},
    )).scalar_one()
    await session.execute(
        text('insert into public.booking_slots (booking_id, time_slot_id, "when", holds_slot) values (:b, :s, :d, :h)'),
        {"b": booking_id, "s": slot_id, "d": when, "h": status != "CANCELLED"},
    )
    return booking_id


# 날짜 옮기기: 예약 규칙은 한국 날짜의 "오늘"로 판단한다 (신청·확정은 수업 전날까지, 완료·노쇼는 수업 당일부터)

class Clock:
    """예약 저장소가 보는 "오늘"을 테스트 안에서 옮긴다 (테스트가 끝나면 원래대로)"""

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self._monkeypatch = monkeypatch

    def set(self, day: date) -> None:
        self._monkeypatch.setattr("app.domains.booking.repository.today_kst", lambda: day)

    def after_lessons(self) -> None:
        """테스트에서 잡은 수업 날짜들이 모두 지난 뒤로 옮긴다. 신청·확정을 마친 다음, 완료·노쇼 전에 부른다"""
        self.set(today_kst() + timedelta(days=30))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    return Clock(monkeypatch)


# 강사·고객 만들기

async def _ensure_instructor(session: AsyncSession, tier: str = "NORMAL") -> uuid.UUID:
    instructor_uuid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users (id, username, email, display_name, is_active, status, role, instructor_tier, feedback_consent)
            VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'INSTRUCTOR', :tier, true)
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
            INSERT INTO public.users (id, username, email, display_name, is_active, status, role, manager_id, feedback_consent)
            VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'CUSTOMER', :manager_id, true)
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


async def _ensure_admin(session: AsyncSession) -> uuid.UUID:
    admin_uuid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.users (id, username, email, display_name, is_active, status, role, feedback_consent)
            VALUES (:id, :username, :email, :display_name, true, 'ACTIVE', 'ADMIN', true)
"""
        ),
        {
            "id": str(admin_uuid),
            "username": f"admin-{admin_uuid.hex[:8]}",
            "email": f"admin-{admin_uuid.hex[:8]}@example.com",
            "display_name": "Test Admin",
        },
    )
    await session.commit()
    return admin_uuid


@pytest_asyncio.fixture
async def admin_id(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with db_conn_and_sessionmaker() as session:
        return await _ensure_admin(session)


@pytest_asyncio.fixture
async def admin_client(
    db_conn_and_sessionmaker: async_sessionmaker[AsyncSession],
    admin_id: uuid.UUID,
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as session:
            yield session

    async def override_get_current_user():
        return CurrentUser(
            id=str(admin_id),
            email=None,
            phone=None,
            username="test-admin",
            display_name="Test Admin",
            role="ADMIN",
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


# 로그인 사용자를 바꿔 가며 호출하는 클라이언트
#   act("이름") 으로 그 사용자가 되어 호출한다. people 에 {이름: (id, 역할)} 을 등록해 쓴다.

async def insert_user(
    session: AsyncSession,
    role: str,
    *,
    manager_id: Optional[uuid.UUID] = None,
    status: str = "ACTIVE",
    **fields,
) -> uuid.UUID:
    uid = uuid.uuid4()
    values = {
        "id": str(uid),
        "username": f"u-{uid.hex[:10]}",
        "email": f"u-{uid.hex[:10]}@example.com",
        "display_name": f"{role.lower()}-{uid.hex[:4]}",
        "is_active": True,
        "status": status,
        "role": role,
        "manager_id": str(manager_id) if manager_id else None,
        "feedback_consent": True,
        **fields,
    }
    cols = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    await session.execute(text(f"insert into public.users ({cols}) values ({params})"), values)
    await session.commit()
    return uid


@pytest_asyncio.fixture
async def actor(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]):
    people: dict[str, tuple[uuid.UUID, str]] = {}
    current: dict = {}

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_conn_and_sessionmaker() as session:
            yield session

    async def override_get_current_user():
        return current["user"]

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[auth_deps.get_current_user] = override_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        def act(name: str) -> AsyncClient:
            uid, role = people[name]
            current["user"] = CurrentUser(
                id=str(uid), email=None, phone=None, username=name, display_name=name,
                role=role, status="ACTIVE", is_active=True,
            )
            return ac
        yield act, people
    app.dependency_overrides.clear()
