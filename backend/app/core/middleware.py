# 요청 로깅 미들웨어: request-id 부여, 처리 시간 기록, 예상 못 한 오류를 한 번만 기록하고 500 응답
from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.exceptions import internal_error_response
from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

# 받은 X-Request-ID 를 그대로 쓰는 조건: 영문·숫자·`.`·`_`·`-` 로 128자 이하.
# 줄바꿈 같은 문자는 로그 줄 위조에, 아주 긴 값은 로그 부풀리기에 쓰일 수 있어 버리고 새로 만든다
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# 이보다 오래 걸린 요청은 WARNING (장애 로그로 거를 수 있게)
SLOW_REQUEST_MS = 1000


def _request_id_from(request: Request) -> str:
    sent = request.headers.get("x-request-id")
    if sent and _REQUEST_ID_RE.fullmatch(sent):
        return sent
    return str(uuid4())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        request_id = _request_id_from(request)
        request.state.request_id = request_id
        token = request_id_var.set(request_id)

        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # 경로에서 처리하지 못한 예외: 여기서 스택을 한 번만 남기고 500 응답을 만든다.
                # 다시 던지면 바깥 처리기와 uvicorn 이 같은 스택을 또 남긴다.
                # Sentry 는 밖으로 나가는 예외를 잡는 방식이라 여기서 직접 보낸다
                sentry_sdk.capture_exception(exc)
                logger.exception("unhandled exception", extra={"method": request.method, "path": request.url.path})
                response = internal_error_response(request_id)

            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

            if response.status_code >= 500:
                level = logging.ERROR
            elif elapsed_ms >= SLOW_REQUEST_MS:
                level = logging.WARNING
            else:
                level = logging.INFO
            logger.log(
                level,
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            return response
        finally:
            request_id_var.reset(token)
