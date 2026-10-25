import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine
async def main():
    async with engine.connect() as c:
        await c.execute(text("select 1"))
        ts = []
        for _ in range(8):
            t = time.perf_counter(); await c.execute(text("select 1")); ts.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    async with engine.connect() as c:
        await c.execute(text("select 1"))
    print(f"쿼리 1번 왕복: 평균 {sum(ts)/len(ts):.0f}ms (최소 {min(ts):.0f} / 최대 {max(ts):.0f})")
    await engine.dispose()
asyncio.run(main())
