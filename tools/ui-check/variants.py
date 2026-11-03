import asyncio, sys, time, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import app.db.session as S
def ssl_ctx():
    ctx = S.ssl.create_default_context(cafile=S.certifi.where())
    ctx.load_verify_locations(cafile=str(S.Path(S.__file__).resolve().parent.parent / "certs" / "prod-ca-2021.crt"))
    return ctx
URL = S.get_async_db_url()
async def bench(name, **kw):
    eng = create_async_engine(URL, connect_args={"ssl": ssl_ctx()}, **kw)
    n = [0]
    event.listen(eng.sync_engine, "before_cursor_execute", lambda *a, **k: n.__setitem__(0, n[0] + 1))
    sm = async_sessionmaker(eng, expire_on_commit=False)
    async with sm() as s: await s.execute(text("select 1"))
    ts = []
    for _ in range(4):
        t = time.perf_counter()
        async with sm() as s: await s.execute(text("select 1"))
        ts.append((time.perf_counter() - t) * 1000)
    print(f"{name}: 새 세션 + 쿼리 1개 = {sum(ts)/len(ts):.0f}ms")
    await eng.dispose()
async def main():
    await bench("pre_ping=True ", pool_size=5, pool_pre_ping=True, pool_recycle=300)
    await bench("pre_ping=False", pool_size=5, pool_pre_ping=False, pool_recycle=300)
asyncio.run(main())
