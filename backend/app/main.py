from __future__ import annotations

import logging
import sys

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.domains.auth.router import router as auth_router
from app.domains.calendar.router import router as calendar_router
from app.domains.calendar.lesson_note_router import router as lesson_note_router
from app.domains.content.router import router as content_router
from app.domains.instructor.router import router as instructor_router
from app.domains.membership.router import router as membership_router
from app.domains.payment.router import router as payment_router
from app.domains.passes.router import router as passes_router
from app.domains.posts.router import router as posts_router
from app.domains.users.router import router as users_router
from app.api.health import router as health_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

# ── Sentry ───────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        send_default_pii=False,
    )
    logger.info("Sentry initialized (env=%s)", settings.SENTRY_ENVIRONMENT)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 미들웨어 (라우터 등록 전에 추가해야 모든 라우트에 적용됨) ──────────────
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

@app.middleware("http")
async def allow_options_preflight(request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=204)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if not settings.CORS_ORIGIN_REGEX else [],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# ── 라우터 (미들웨어 설정 이후 등록) ─────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(instructor_router)
app.include_router(calendar_router)
app.include_router(lesson_note_router)
app.include_router(membership_router)
app.include_router(payment_router)
app.include_router(passes_router)
app.include_router(posts_router)
app.include_router(content_router)

logger.info("CORS origins: %s", settings.cors_origins)
logger.info("CORS regex: %s", settings.CORS_ORIGIN_REGEX)

@app.get("/")
async def root():
    return {"status": "ok"}
