import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from datetime import date, timedelta
from sqlalchemy import event
from httpx import ASGITransport, AsyncClient
from app.db.session import engine
from app.main import app
HID = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "hid.txt")).read().strip()
stmts = []
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _b(conn, cursor, statement, params, context, executemany):
    stmts.append(statement.split()[0] + " " + " ".join(statement.split()[1:6]))
async def main():
    url = f"/calendars/{HID}/availability?start={date.today()}&end={date.today()+timedelta(days=6)}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.get(url)                       # 연결 데우기
        for label in ("2번째", "3번째"):
            stmts.clear(); t = time.perf_counter()
            r = await c.get(url)
            print(f"{label} 요청: {r.status_code} {(time.perf_counter()-t)*1000:.0f}ms, SQL {len(stmts)}개")
    for s in stmts: print("   ", s[:100])
    await engine.dispose()
asyncio.run(main())
