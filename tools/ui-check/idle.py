import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import app.db.session as S
def ssl_ctx():
    ctx = S.ssl.create_default_context(cafile=S.certifi.where())
    ctx.load_verify_locations(cafile=str(S.Path(S.__file__).resolve().parent.parent / "certs" / "prod-ca-2021.crt"))
    return ctx
async def probe(minutes):
    eng = create_async_engine(S.get_async_db_url(), connect_args={"ssl": ssl_ctx()}, pool_size=1, pool_pre_ping=False)
    async with eng.connect() as c:
        await c.execute(text("select 1"))
    await asyncio.sleep(minutes * 60)
    t = time.perf_counter()
    try:
        async with eng.connect() as c:
            await c.execute(text("select 1"))
        res = f"정상 ({(time.perf_counter()-t)*1000:.0f}ms)"
    except Exception as e:
        res = f"실패: {type(e).__name__}"
    print(f"{minutes}분 쉰 연결: {res}", flush=True)
    await eng.dispose()
async def main():
    await asyncio.gather(*(probe(m) for m in (1, 3, 6, 10)))
asyncio.run(main())
