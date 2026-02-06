from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        # 클라이언트가 X-Request-ID를 보내면 그걸 쓰고, 없으면 생성
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # 예외 발생도 로깅하고 그대로 다시 raise (전역 exception handler가 응답 처리)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
                request_id,
                request.method,
                request.url.path,
                500,
                elapsed_ms,
                request.client.host if request.client else None,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 응답 헤더에 request-id/처리시간을 넣어두면 디버깅이 쉬움
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
            request.client.host if request.client else None,
        )
        return response
