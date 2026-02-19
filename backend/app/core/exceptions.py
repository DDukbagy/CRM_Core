from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _error(code: str, message: str, details: Any = None, request_id: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    if request_id:
        payload["error"]["request_id"] = request_id
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 401/403/404 등은 절대 500으로 바뀌면 안 됨
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error(code="HTTP_EXCEPTION", message=str(exc.detail), request_id=request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=_error(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=exc.errors(),
                request_id=request_id,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        request_id = getattr(request.state, "request_id", None)

        orig = getattr(exc, "orig", None)
        orig_type = type(orig).__name__ if orig is not None else ""
        orig_msg = str(orig) if orig is not None else str(exc)

        is_unique = "UniqueViolationError" in orig_type or "duplicate key value" in orig_msg.lower()
        if is_unique:
            return JSONResponse(
                status_code=409,
                content=_error(
                    code="UNIQUE_CONSTRAINT_VIOLATION",
                    message="Resource conflict (duplicate).",
                    request_id=request_id,
                ),
            )

        return JSONResponse(
            status_code=400,
            content=_error(
                code="INTEGRITY_ERROR",
                message="Database integrity error.",
                details=orig_msg,
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        - Exception 핸들러는 1개만 둔다 (중복 등록 금지)
        - HTTPException은 이미 위에서 처리되므로 여기서 다시 건드리지 않는다
        - 로그에는 request_id를 포함해 추적 가능하게 한다
        """
        request_id = getattr(request.state, "request_id", None)
        path_params = dict(getattr(request, "path_params", {}) or {})

        user_id = None
        try:
            user = getattr(request.state, "user", None)
            if user and getattr(user, "id", None):
                user_id = str(user.id)
        except Exception:
            user_id = None

        # uvicorn.error에도 남기면 ECS/CloudWatch에서 찾기 쉬움
        uvicorn_logger = logging.getLogger("uvicorn.error")
        uvicorn_logger.exception(
            "Unhandled exception request_id=%s method=%s path=%s path_params=%s user_id=%s",
            request_id,
            request.method,
            request.url.path,
            path_params,
            user_id,
        )

        logger.exception(
            "Unhandled exception request_id=%s method=%s path=%s path_params=%s user_id=%s",
            request_id,
            request.method,
            request.url.path,
            path_params,
            user_id,
            exc_info=exc,
        )

        return JSONResponse(
            status_code=500,
            content=_error(
                code="INTERNAL_SERVER_ERROR",
                message="Unexpected server error.",
                request_id=request_id,
            ),
        )
