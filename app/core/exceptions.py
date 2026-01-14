from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _error(code: str, message: str, details: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # HTTPException 응답 포맷 통일
        return JSONResponse(
            status_code=exc.status_code,
            content=_error(code="HTTP_EXCEPTION", message=str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 422 validation 에러 포맷 통일
        return JSONResponse(
            status_code=422,
            content=_error(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        # 유니크 충돌(중복 예약 등)을 409로 매핑
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
                ),
            )

        # 그 외 무결성 오류
        return JSONResponse(
            status_code=400,
            content=_error(
                code="INTEGRITY_ERROR",
                message="Database integrity error.",
                details=orig_msg,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 예상 못한 에러는 반드시 로그에 남기기 (uvicorn.error로도 찍어서 Copilot logs에서 보이게)
        uvicorn_logger = logging.getLogger("uvicorn.error")

        # request context도 같이 남기면 장애 재현이 훨씬 쉬움
        uvicorn_logger.exception(
            "Unhandled exception path=%s method=%s",
            getattr(request.url, "path", None),
            getattr(request, "method", None),
            exc_info=exc,
        )
        logger.exception("Unhandled exception", exc_info=exc)

        return JSONResponse(
            status_code=500,
            content=_error(code="INTERNAL_SERVER_ERROR", message="Unexpected server error."),
        )
