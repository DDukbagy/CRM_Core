from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import HTTPException
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

        except HTTPException as e:
            # 401/403 등은 "정상적인" 예외 흐름일 수 있으니 error 로깅 대신 warning 정도로만 남김
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
                request_id,
                request.method,
                request.url.path,
                getattr(e, "status_code", 500),
                elapsed_ms,
                request.client.host if request.client else None,
            )
            raise

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
            response.status_code,
            elapsed_ms,
            request.client.host if request.client else None,
        )
        return response
