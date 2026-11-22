# 전역 예외 처리: 오류 응답 형식 통일, 예상 못한 오류 로깅
from __future__ import annotations

import json
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


# 앱에 예외 처리기 등록
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 401/403/404 등은 절대 500으로 바뀌면 안 됨
        request_id = getattr(request.state, "request_id", None)
        # detail 이 {"error": 코드, "message": 문장, ...} 묶음이면 풀어서 내보낸다 (예: 예약 충돌 SLOT_ALREADY_BOOKED).
        # 통째로 문자열로 바꾸면 화면에 보여 줄 수 없는 메시지가 된다. 나머지 값은 details 로 넘긴다
        if isinstance(exc.detail, dict) and "message" in exc.detail:
            extra = {k: v for k, v in exc.detail.items() if k not in ("error", "message")}
            content = _error(
                code=str(exc.detail.get("error", "HTTP_EXCEPTION")), message=str(exc.detail["message"]),
                details=extra or None, request_id=request_id,
            )
        else:
            content = _error(code="HTTP_EXCEPTION", message=str(exc.detail), request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        # 검증 오류 정보에 JSON 으로 바꿀 수 없는 객체가 섞일 수 있어 문자열로 바꿔 내보낸다
        safe_errors = json.loads(json.dumps(exc.errors(), default=str))
        return JSONResponse(
            status_code=422,
            content=_error(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=safe_errors,
                request_id=request_id,
            ),
        )

    # DB 제약 위반은 409 로
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
        """요청 로그 미들웨어(RequestLoggingMiddleware) 바깥에서 난 예외만 여기로 온다.
        경로 안의 예외는 미들웨어가 스택을 한 번 남기고 500 응답을 만든다 (middleware.py).
        """
        logger.exception(
            "Unhandled exception method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return internal_error_response(getattr(request.state, "request_id", None))


def internal_error_response(request_id: str | None) -> JSONResponse:
    """예상 못 한 오류의 500 응답. 사용자가 알려 준 요청 ID 로 로그를 찾을 수 있게 본문과 헤더에 넣는다"""
    return JSONResponse(
        status_code=500,
        content=_error(
            code="INTERNAL_SERVER_ERROR",
            message="Unexpected server error.",
            request_id=request_id,
        ),
        headers={"X-Request-ID": request_id} if request_id else None,
    )
