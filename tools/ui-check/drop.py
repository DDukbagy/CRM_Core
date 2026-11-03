# 풀에 있던 연결을 DB 쪽에서 강제로 끊은 뒤 다음 요청들이 어떻게 되는지
import asyncio, sys, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine, AsyncSessionLocal
async def q():
    async with AsyncSessionLocal() as s:
        return (await s.execute(text("select pg_backend_pid()"))).scalar()
async def main():
    pid = await q(); print(f"풀 연결 사용: 정상 (pid {pid})")
    import asyncpg   # 풀 밖의 별도 연결로 위 연결을 끊음 (DB 재시작·pooler 끊김 흉내)
    k = await asyncpg.connect(engine.url.set(drivername="postgresql").render_as_string(hide_password=False), ssl=False)
    await k.execute(f"select pg_terminate_backend({pid})"); await k.close()
    for i in (1, 2, 3):
        try: print(f"끊긴 뒤 {i}번째 요청: 정상 (pid {await q()})")
        except Exception as e: print(f"끊긴 뒤 {i}번째 요청: 실패 {type(e).__name__}")
    await engine.dispose()
asyncio.run(main())
