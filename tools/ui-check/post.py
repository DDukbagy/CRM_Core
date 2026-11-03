import asyncio, sys, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine
async def main():
    async with engine.connect() as c:
        q = lambda s: c.execute(text(s))
        print("promotions:", (await q("select to_regclass('public.promotions') is not null")).scalar(),
              "| RLS 꺼진 테이블:", (await q("select count(*) from pg_tables where schemaname='public' and not rowsecurity")).scalar(),
              "| 회원:", (await q("select count(*) from users")).scalar())
    await engine.dispose()
asyncio.run(main())
