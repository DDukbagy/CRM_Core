import asyncio, sys, logging
sys.path.insert(0, "."); logging.disable(logging.CRITICAL)
from sqlalchemy import text
from app.db.session import engine
async def main():
    async with engine.connect() as c:
        r = (await c.execute(text("select relrowsecurity from pg_class where oid='public.users'::regclass"))).scalar()
        pols = (await c.execute(text("select policyname, cmd, roles::text from pg_policies where schemaname='public' and tablename='users'"))).all()
        grants = (await c.execute(text("select grantee, privilege_type from information_schema.role_table_grants where table_schema='public' and table_name='users' and grantee in ('anon','authenticated')"))).all()
    print("users RLS 켜짐:", r); print("users 정책:", pols or "없음"); print("authenticated/anon 권한:", sorted({f"{g}:{p}" for g,p in grants}))
    await engine.dispose()
asyncio.run(main())
