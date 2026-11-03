"""화면 점검용 데이터 → ids.json"""
import asyncio, json, os, uuid
from datetime import date, timedelta
import asyncpg, httpx

API = "http://127.0.0.1:8000"; AUTH = "http://127.0.0.1:54321/auth/v1/token?grant_type=password"
DSN = os.environ["MOCK_DB_DSN"]; OUT = os.path.join(os.path.dirname(__file__), "ids.json")
PEOPLE = [("admin", "ADMIN", "ACTIVE", "관리자"), ("kim", "INSTRUCTOR", "PENDING", "김프로"), ("lee", "INSTRUCTOR", "PENDING", "이코치"),
          ("c1", "CUSTOMER", "ACTIVE", "최고객"), ("c2", "CUSTOMER", "ACTIVE", "정고객"), ("c6", "CUSTOMER", "ACTIVE", "한고객")]


async def main():
    db = await asyncpg.connect(DSN); ids = {}
    for key, role, status, name in PEOPLE:
        uid = uuid.uuid4()
        await db.execute("insert into public.users (id, username, email, display_name, phone, role, status, is_active, feedback_consent)"
                         " values ($1,$2,$3,$4,$5,$6,$7,true,true)", uid, key, f"{key}@example.com", name, f"010-9{len(ids):03d}-0000", role, status)
        ids[key] = str(uid)
    fails = []
    async with httpx.AsyncClient(timeout=20) as http:
        tok = {k: (await http.post(AUTH, json={"email": f"{k}@example.com", "password": "test1234"})).json()["access_token"] for k, *_ in PEOPLE}

        async def call(who, method, path, **kw):
            r = await http.request(method, API + path, headers={"Authorization": f"Bearer {tok[who]}"}, **kw)
            if r.status_code >= 400: fails.append(f"{method} {path}: {r.status_code} {r.text[:150]}")
            return r.json() if r.content else None

        for i in ("kim", "lee"):
            await call("admin", "POST", f"/instructors/{ids[i]}/approve")
        for c in ("c1", "c2"):
            await call("kim", "POST", "/users/me/customers", json={"email": f"{c}@example.com"})
        pt = await call("kim", "POST", "/passes/types", json={"name": "10회권", "duration_hours": 1, "session_count": 10, "price": 500000})
        await call("kim", "POST", "/passes/types", json={"name": "20회권", "duration_hours": 1, "session_count": 20, "price": 900000})
        cp = await call("kim", "POST", "/passes/assign", json={"customer_id": ids["c1"], "pass_type_id": pt["id"]})
        await call("kim", "POST", "/payments", json={"customer_id": ids["c1"], "customer_pass_id": cp["id"], "amount": 500000, "method": "CASH"})
        await call("kim", "POST", "/payments", json={"customer_id": ids["c2"], "amount": 120000, "method": "TRANSFER"})
        await call("kim", "POST", "/lesson-notes", json={"customer_id": ids["c1"], "title": "1회차", "content": "어드레스 자세"})
        room = await call("c1", "POST", "/chat/rooms", json={"instructor_id": ids["kim"]})
        await call("c1", "POST", f"/chat/rooms/{room['id']}/messages", json={"content": "레슨 문의드려요"})
        ids.update(pass_type=pt["id"], customer_pass=cp["id"], room=room["id"])
    # 지난달 결제 1건 (월별 그래프 확인용)
    last = (date.today().replace(day=1) - timedelta(days=3))
    await db.execute("insert into public.payments (customer_id, amount, method, status, created_at, updated_at) values ($1, 300000, 'CASH', 'COMPLETED', $2, $2)",
                     uuid.UUID(ids["c2"]), __import__("datetime").datetime(last.year, last.month, last.day, 12, tzinfo=__import__("datetime").timezone.utc))
    await db.close()
    json.dump(ids, open(OUT, "w"), indent=1)
    print("seed 실패", len(fails), *fails, sep="\n")


asyncio.run(main())
