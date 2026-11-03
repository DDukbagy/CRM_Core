"""로컬 화면 점검용 가짜 Supabase (Auth + users 역할 조회만). 실제 Supabase 에는 접속하지 않는다"""
import os, time, uuid
import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from jose import jwt

SECRET = os.environ["SUPABASE_JWT_SECRET"]; AUD = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
ISS = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1"; DSN = os.environ["MOCK_DB_DSN"]; PASSWORD = "test1234"
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
pool = None

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=4)

def _user(uid, email):
    return {"id": uid, "aud": AUD, "role": "authenticated", "email": email, "email_confirmed_at": "2026-01-01T00:00:00Z",
            "app_metadata": {"provider": "email", "providers": ["email"]}, "user_metadata": {}, "identities": [],
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}

def _session(uid, email):
    now = int(time.time())
    c = {"sub": uid, "email": email, "aud": AUD, "iss": ISS, "role": "authenticated", "iat": now, "exp": now + 3600, "session_id": str(uuid.uuid4())}
    return {"access_token": jwt.encode(c, SECRET, algorithm="HS256"), "token_type": "bearer", "expires_in": 3600, "expires_at": now + 3600,
            "refresh_token": f"rt-{uid}", "user": _user(uid, email)}

def _err(st, code, msg): return JSONResponse({"code": st, "error_code": code, "msg": msg}, status_code=st)

async def _claims(req):
    a = req.headers.get("authorization", "")
    if not a.lower().startswith("bearer "): return None
    try: return jwt.decode(a[7:], SECRET, algorithms=["HS256"], audience=AUD)
    except Exception: return None

@app.post("/auth/v1/token")
async def token(req: Request):
    g = req.query_params.get("grant_type"); b = await req.json()
    if g == "password":
        r = await pool.fetchrow("select id::text, email from public.users where lower(email)=lower($1)", b.get("email") or "")
        if not r or b.get("password") != PASSWORD: return _err(400, "invalid_credentials", "Invalid login credentials")
        return _session(r["id"], r["email"])
    if g == "refresh_token":
        r = await pool.fetchrow("select id::text, email from public.users where id::text=$1", (b.get("refresh_token") or "").removeprefix("rt-"))
        return _session(r["id"], r["email"] or "") if r else _err(400, "refresh_token_not_found", "Invalid Refresh Token")
    return _err(400, "unsupported_grant_type", "unsupported")

@app.get("/auth/v1/user")
async def user(req: Request):
    c = await _claims(req)
    return _user(c["sub"], c.get("email") or "") if c else _err(401, "bad_jwt", "invalid JWT")

@app.post("/auth/v1/logout")
async def logout(): return Response(status_code=204)

@app.get("/rest/v1/users")
async def users_role(req: Request):
    c = await _claims(req); uid = req.query_params.get("id", "").removeprefix("eq."); rows = []
    if c and c["sub"] == uid:
        r = await pool.fetchrow("select role from public.users where id::text=$1", uid); rows = [{"role": r["role"]}] if r else []
    if "vnd.pgrst.object" in req.headers.get("accept", ""):
        return rows[0] if len(rows) == 1 else JSONResponse({"code": "PGRST116", "message": "no rows"}, status_code=406)
    return rows
