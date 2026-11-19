"""측정용 서버 실행기: 앱 코드를 바꾸지 않고 DB 연결 방식만 골라 띄운다

  POOL=pool  (기본) app/db/session.py 의 커넥션 풀 5+5 그대로 = 개선 후
  POOL=null  이 프로세스에서만 엔진을 NullPool(요청마다 새 연결)로 바꾼다 = 개선 전
요청 제한(slowapi)은 두 경우 모두 끈다 (아래 설명)

get_session 은 부를 때마다 session 모듈의 AsyncSessionLocal 을 찾으므로, app.main 을 불러오기 전에 바꿔 두면 모든 요청이 바뀐 엔진을 쓴다.
실행: make apiload 가 부른다 (직접 실행은 PORT, POOL 환경변수와 함께 python loadtest/serve.py)
"""
from __future__ import annotations

import os
import sys

import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import session  # noqa: E402

pool = os.environ.get("POOL", "pool")
if pool == "null":
    session.engine = create_async_engine(
        session.get_async_db_url(), poolclass=NullPool, connect_args={"ssl": None}
    )
    session.AsyncSessionLocal = async_sessionmaker(
        bind=session.engine, class_=AsyncSession, expire_on_commit=False
    )
elif pool != "pool":
    raise SystemExit("POOL 은 pool 또는 null")

from app.main import app  # noqa: E402

# 요청 제한(IP 당 분당 200개)을 끈다. 가상 사용자 전원이 같은 IP(127.0.0.1)라 합쳐서 제한에 걸리기 때문이다.
# 실제 사용자는 IP 가 각자 다르고, 가상 사용자 한 명은 분당 약 60개라 혼자서는 제한에 닿지 않는다
app.state.limiter.enabled = False

print(f"DB 연결 방식: {pool} ({type(session.engine.pool).__name__}), 요청 제한 꺼짐", flush=True)
uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8770")), log_level="warning", access_log=False)
