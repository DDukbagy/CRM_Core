from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_put_push_token(client):
    """PUT /users/me/push-token → 204, 토큰 저장."""
    res = await client.put("/users/me/push-token", json={"token": "ExponentPushToken[test-abc123]"})
    assert res.status_code == 204, res.text


async def test_put_push_token_null(client):
    """PUT /users/me/push-token with null token → 204 (토큰 초기화)."""
    res = await client.put("/users/me/push-token", json={"token": None})
    assert res.status_code == 204, res.text


async def test_delete_push_token(client):
    """DELETE /users/me/push-token → 204, 토큰 삭제."""
    await client.put("/users/me/push-token", json={"token": "ExponentPushToken[test-abc123]"})
    res = await client.delete("/users/me/push-token")
    assert res.status_code == 204, res.text


async def test_get_me(client):
    """GET /users/me → 200, 현재 유저 정보 반환."""
    res = await client.get("/users/me")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "id" in body
    assert "role" in body
