from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.posts.models import Post


async def _insert_user(session: AsyncSession, role: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role, feedback_consent)
            values (:id, :username, :email, :display_name, true, 'ACTIVE', :role, true)
            """
        ),
        {
            "id": str(user_id),
            "username": f"consent-{user_id.hex[:8]}",
            "email": f"consent-{user_id.hex[:8]}@example.com",
            "display_name": f"consent-{user_id.hex[:8]}",
            "role": role,
        },
    )
    await session.commit()
    return user_id


async def _create_feedback_post(session: AsyncSession, customer_id: uuid.UUID) -> uuid.UUID:
    instructor_id = await _insert_user(session, "INSTRUCTOR")
    post = Post(
        instructor_id=instructor_id,
        created_by_user_id=instructor_id,
        type="FEEDBACK",
        title="pytest-consent",
        customer_id=customer_id,
        is_public=False,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return uuid.UUID(str(post.id))


@pytest_asyncio.fixture
async def post_id(client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    """
    테스트용 비공개 FEEDBACK 게시물 1개 생성.
    대상 고객을 client 의 테스트 유저로 맞춰서
    grant/revoke가 '피드백 대상 고객' 권한으로 동작하게 만든다.
    """
    me = (await client.get("/auth/me")).json()
    async with db_conn_and_sessionmaker() as session:
        return await _create_feedback_post(session, uuid.UUID(me["id"]))


@pytest.mark.asyncio
async def test_grant_sets_public(client, post_id: uuid.UUID):
    r = await client.post(f"/posts/{post_id}/consent/grant")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_public"] is True


@pytest.mark.asyncio
async def test_public_get_without_token_is_200(client, post_id: uuid.UUID):
    await client.post(f"/posts/{post_id}/consent/grant")

    # 무토큰 조회(Authorization 헤더 없음)
    r = await client.get(f"/posts/{post_id}")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_revoke_sets_private(client, post_id: uuid.UUID):
    await client.post(f"/posts/{post_id}/consent/grant")

    r = await client.post(f"/posts/{post_id}/consent/revoke")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_public"] is False


@pytest.mark.asyncio
async def test_private_get_without_token_is_blocked(client, post_id: uuid.UUID):
    # 비공개 상태 보장
    await client.post(f"/posts/{post_id}/consent/revoke")

    # 무토큰 조회는 401/403
    r = await client.get(f"/posts/{post_id}")
    assert r.status_code in (401, 403), r.text


@pytest.mark.asyncio
async def test_only_target_customer_can_grant(
    client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    # 다른 고객이 대상인 피드백은 동의를 바꿀 수 없다
    async with db_conn_and_sessionmaker() as session:
        other_customer = await _insert_user(session, "CUSTOMER")
        other_post_id = await _create_feedback_post(session, other_customer)

    r = await client.post(f"/posts/{other_post_id}/consent/grant")
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_consent_only_applies_to_feedback(
    client, db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]
):
    async with db_conn_and_sessionmaker() as session:
        instructor_id = await _insert_user(session, "INSTRUCTOR")
        post = Post(instructor_id=instructor_id, type="PROMOTION", title="promo", is_public=True)
        session.add(post)
        await session.commit()
        await session.refresh(post)

    r = await client.post(f"/posts/{post.id}/consent/revoke")
    assert r.status_code == 400, r.text
