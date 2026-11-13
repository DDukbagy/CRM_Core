# Expo 푸시 알림 발송 (Expo Push API: https://docs.expo.dev/push-notifications/sending-notifications/)
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
# 앱 app.json 의 expo-notifications 플러그인 defaultChannel 과 같은 이름 (Android)
ANDROID_CHANNEL_ID = "default"
# 기기에서 앱이 지워졌거나 토큰이 만료됨 → 이 토큰으로 더는 보내면 안 된다
DEVICE_NOT_REGISTERED = "DeviceNotRegistered"

_TOKEN_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


def is_expo_push_token(token: Optional[str]) -> bool:
    """Expo 푸시 토큰 형식인지 (ExponentPushToken[...] / ExpoPushToken[...])"""
    return bool(token) and token.startswith(_TOKEN_PREFIXES) and token.endswith("]")  # type: ignore[union-attr]


def build_message(token: str, title: str, body: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {
        "to": token,
        "title": title,
        "body": body,
        "data": data or {},
        "sound": "default",
        "priority": "high",
        "channelId": ANDROID_CHANNEL_ID,
    }


def _ticket_error(payload: Any) -> Optional[str]:
    """응답의 push ticket 이 error 면 오류 코드(없으면 "error"), 정상이면 None"""
    ticket = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(ticket, list):  # 여러 건을 보낸 형식
        ticket = ticket[0] if ticket else None
    if not isinstance(ticket, dict) or ticket.get("status") != "error":
        return None
    details = ticket.get("details") or {}
    code = details.get("error") if isinstance(details, dict) else None
    logger.warning("Expo push ticket error: code=%s message=%s", code, str(ticket.get("message", ""))[:200])
    return code or "error"


async def send_push(
    token: str | None,
    title: str,
    body: str,
    data: dict | None = None,
) -> Optional[str]:
    """
    Expo Push 발송. 알림은 부가 기능이라 실패해도 예외를 전파하지 않는다.
    반환: None = 보냄(또는 보낼 토큰 없음), 그 외 = 오류 코드 (예: DEVICE_NOT_REGISTERED)
    """
    if not is_expo_push_token(token):
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                EXPO_PUSH_URL,
                json=build_message(token, title, body, data),  # type: ignore[arg-type]
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        if resp.status_code >= 400:
            logger.warning("Expo push failed: status=%s body=%s", resp.status_code, resp.text[:200])
            return "http_error"
        try:
            return _ticket_error(resp.json())
        except ValueError:
            logger.warning("Expo push: invalid JSON response")
            return "invalid_response"
    except Exception as exc:
        logger.warning("Push notification error: %s", exc)
        return "network_error"
