import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine, AsyncSessionLocal
async def main():
    async with AsyncSessionLocal() as s:
        await s.execute(text("select 1"))
        for i in range(3):
            t=time.perf_counter(); await s.execute(text("select 1")); print(f"같은 세션 안 쿼리: {(time.perf_counter()-t)*1000:.0f}ms")
    for i in range(3):
        t=time.perf_counter()
        async with AsyncSessionLocal() as s:
            t1=time.perf_counter(); await s.execute(text("select 1")); t2=time.perf_counter()
        t3=time.perf_counter()
        print(f"새 세션: 첫 쿼리(연결 꺼내기·핑·BEGIN 포함) {(t2-t1)*1000:.0f}ms, 닫기(ROLLBACK) {(t3-t2)*1000:.0f}ms, 합계 {(t3-t)*1000:.0f}ms")
    await engine.dispose()
asyncio.run(main())
