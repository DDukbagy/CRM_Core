from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.posts.models import Post


@pytest_asyncio.fixture
async def post_id(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    """
    테스트용 PRIVATE 게시물 1개 생성.
    owner_user_id == created_by_user_id 로 맞춰서
    grant/revoke가 'owner' 권한으로 동작하게 만든다.
    """
    async with db_conn_and_sessionmaker() as session:
        res = await session.execute(text("select id from public.users limit 1"))
        row = res.first()
        assert row and row[0], "public.users에 테스트 유저가 없습니다."
        user_id = uuid.UUID(str(row[0]))

        post = Post(
            owner_user_id=user_id,
            created_by_user_id=user_id,
            caption="pytest-consent",
            status="PRIVATE",
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        return uuid.UUID(str(post.id))


@pytest.mark.asyncio
async def test_grant_sets_public(client, post_id: uuid.UUID):
    r = await client.post(f"/posts/{post_id}/consent/grant")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "PUBLIC"


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
    assert data["status"] == "PRIVATE"


@pytest.mark.asyncio
async def test_private_get_without_token_is_blocked(client, post_id: uuid.UUID):
    # PRIVATE 상태 보장
    await client.post(f"/posts/{post_id}/consent/revoke")

    # 무토큰 조회는 401/403
    r = await client.get(f"/posts/{post_id}")
    assert r.status_code in (401, 403), r.text
