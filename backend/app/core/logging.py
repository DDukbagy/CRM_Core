# 로그 설정: 형식(json·text), 요청 ID 연결, 사용 로그(누가 무엇을 했나)
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# 요청마다 미들웨어가 넣는 요청 ID. 같은 요청에서 남는 모든 로그에 붙는다
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# LogRecord 가 원래 가진 속성. 이 밖의 속성(extra=...)이 로그의 칸이 된다 (color_message 는 uvicorn 의 터미널 색상용 사본)
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "color_message"}

_event_logger = logging.getLogger("app.event")


def _fields(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS and not k.startswith("_")}


class RequestIdFilter(logging.Filter):
    """요청 안에서 남은 로그에 request_id 칸을 채운다 (이미 있으면 그대로)"""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            rid = request_id_var.get()
            if rid is not None:
                record.request_id = rid
        return True


class JsonFormatter(logging.Formatter):
    """로그 한 줄 = JSON 객체 하나. CloudWatch·Render 에서 칸으로 거를 수 있다"""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_fields(record),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """로컬 개발용: `시각 레벨 로거 메시지 칸=값 ...`"""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = " ".join(f"{k}={v}" for k, v in _fields(record).items())
        if not fields:
            return line
        # 스택 트레이스가 붙으면 첫 줄(메시지) 뒤에 칸을 넣는다
        head, sep, rest = line.partition("\n")
        return f"{head} {fields}{sep}{rest}"


def build_formatter(fmt: str) -> logging.Formatter:
    return TextFormatter() if fmt == "text" else JsonFormatter()


def configure_logging(fmt: str) -> None:
    """루트 로거에 stdout 핸들러 하나. uvicorn 로그도 같은 형식으로 모은다"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(build_formatter(fmt))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    # 요청 로그는 app.request 가 남기므로 uvicorn 접근 로그는 끈다 (같은 요청이 두 줄이 되지 않게)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_event(event: str, **fields: Any) -> None:
    """사용 로그: 예약·수강권·결제에서 실제로 일어난 일(또는 거부된 시도). 사람은 ID 로만 남긴다 (이메일·전화번호 금지)

    상태가 바뀌는 일은 commit 이 끝난 뒤에 부른다 (실패해 되돌린 일을 기록하지 않게).
    """
    _event_logger.info(event, extra={"event": event, **fields})
