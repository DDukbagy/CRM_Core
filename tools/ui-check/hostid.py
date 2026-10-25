import asyncio, sys, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine
async def main():
    async with engine.connect() as c:
        print((await c.execute(text("select host_id::text from calendars order by id limit 1"))).scalar())
    await engine.dispose()
asyncio.run(main())
