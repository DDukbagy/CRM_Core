from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(
    token: str | None,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """Expo Push Notification 발송. 토큰이 없거나 실패해도 예외 전파 안 함."""
    if not token or not token.startswith("ExponentPushToken["):
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                EXPO_PUSH_URL,
                json={
                    "to": token,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "sound": "default",
                },
            )
            if resp.status_code >= 400:
                logger.warning("Expo push failed: status=%s body=%s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Push notification error: %s", exc)
