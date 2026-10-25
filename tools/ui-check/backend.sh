#!/usr/bin/env bash
# 로컬 DB(crm_ui) 새로 만들기 → 가짜 Supabase(54321) + 백엔드(8000) → 시드
set -e
H="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$H/logs" "$H/shots"; R="$(cd "$H/../.." && pwd)"
bash $H/killport.sh 8000 54321; sleep 1
cd $R/backend
bash scripts/local_db.sh recreate crm_ui | tail -1
export LOCAL_DB_NAME=crm_ui; source scripts/local_env.sh
export SUPABASE_URL=http://127.0.0.1:54321 MOCK_DB_DSN="postgresql://postgres:postgres@127.0.0.1:${LOCAL_DB_PORT}/crm_ui"
(setsid .venv/bin/python -m uvicorn mock_supabase:app --app-dir $H --host 127.0.0.1 --port 54321 > $H/logs/mock.log 2>&1 &)
(setsid .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > $H/logs/api.log 2>&1 &)
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:8000/health && curl -s -o /dev/null http://127.0.0.1:54321/docs && break; sleep 1; done
.venv/bin/python $H/seed.py
