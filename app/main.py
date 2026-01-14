from __future__ import annotations

import logging
import sys

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

from app.domains.account.router import router as account_router
from app.domains.calendar.router import router as calendar_router
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.domains.auth.router import router as auth_router
from app.domains.instructor.router import router as instructor_router
from app.domains.posts.router import router as posts_router
from app.api.health import router as health_router

# ---- Logging: always emit app logs to stdout (works well in ECS/Copilot) ----
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# Make sure our app logger isn't silenced
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger(__name__).setLevel(logging.INFO)

app = FastAPI()

app.include_router(instructor_router)
app.include_router(posts_router)
app.include_router(health_router)

app.add_middleware(RequestLoggingMiddleware)

# CORS (운영에서는 허용 도메인만 넣는 방식으로 좁히는 게 정석)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],    # allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],    # allow_headers=["Authorization", "Content-Type"],
)

register_exception_handlers(app)

@app.get("/")
async def root():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(account_router)
app.include_router(calendar_router)
