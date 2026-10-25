import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine
async def main():
    ts = []
    for _ in range(4):
        t = time.perf_counter()
        async with engine.connect() as c:
            await c.execute(text("select 1"))
        ts.append((time.perf_counter() - t) * 1000)
    print(f"새 연결 + 쿼리 1번: 평균 {sum(ts[1:])/3:.0f}ms (첫 번째 {ts[0]:.0f}ms)")
    await engine.dispose()
asyncio.run(main())
