#!/usr/bin/env bash
# 원클릭 로컬 검증: 로컬 DB → 마이그레이션 → 서버 실행 → 토큰 → 주요 흐름(run_flow.sh) → 서버 종료
#
# - 외부 서비스(Supabase·AWS) 없이 scripts/local_env.sh 의 로컬 더미 설정으로 실행한다.
#   backend/.env 와 원격 DB는 쓰지 않는다.
# - 토큰은 로컬 더미 Supabase 비밀값으로 직접 서명한다 (실제 Supabase 로그인 토큰은 make apitoken).
# - 사용: make apiverify   (포트 변경: VERIFY_PORT=8766 make apiverify)
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"
export LOCAL_DB_NAME=crm_verify
source scripts/local_env.sh

PORT="${VERIFY_PORT:-8765}"
export BASE_URL="http://127.0.0.1:${PORT}"
LOG_DIR="$BACKEND_DIR/.tmp"
LOG_FILE="$LOG_DIR/verify_server.log"
SERVER_PGID=""

log() { echo -e "✅ $*"; }
err() { echo -e "❌ $*" >&2; }

stop_server() {
  # setsid 로 띄운 프로세스 그룹 전체(poetry → uvicorn)를 종료한다
  if [ -n "$SERVER_PGID" ]; then
    kill -- "-$SERVER_PGID" >/dev/null 2>&1 || true
    SERVER_PGID=""
  fi
}
trap stop_server EXIT

if curl -s -o /dev/null "$BASE_URL/health"; then
  err "포트 $PORT 를 이미 다른 프로세스가 쓰고 있습니다. VERIFY_PORT 로 다른 포트를 지정하세요."
  exit 1
fi

log "1) 로컬 DB 준비 ($LOCAL_DB_NAME, 마이그레이션 head)"
bash scripts/local_db.sh recreate "$LOCAL_DB_NAME"

log "2) 서버 실행 ($BASE_URL)"
mkdir -p "$LOG_DIR"
setsid poetry run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PGID="$!"
for _ in $(seq 1 30); do
  curl -sf -o /dev/null "$BASE_URL/health/db" && break
  sleep 1
done
curl -sf -o /dev/null "$BASE_URL/health/db" || { err "서버가 30초 안에 준비되지 않았습니다. 로그: $LOG_FILE"; exit 1; }

log "3) 토큰 발급 (관리자·강사·고객) 및 강사 승인"
eval "$(poetry run python - <<'PY'
import os, time, uuid
from jose import jwt

def token(sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "email": email, "aud": os.environ["SUPABASE_JWT_AUDIENCE"],
         "iss": os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1", "iat": now, "exp": now + 1800},
        os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256",
    )

host_id, guest_id = str(uuid.uuid4()), str(uuid.uuid4())
print(f"export ADMIN_TOKEN={token(str(uuid.uuid4()), os.environ['SUPER_ADMIN_EMAIL'])}")
print(f"export HOST_ID={host_id}")
print(f"export HOST_TOKEN={token(host_id, f'verify-host-{host_id[:8]}@example.com')}")
print(f"export GUEST_TOKEN={token(guest_id, f'verify-guest-{guest_id[:8]}@example.com')}")
PY
)"

call() {  # call METHOD PATH TOKEN 기대코드
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" -X "$1" "$BASE_URL$2" -H "Authorization: Bearer $3")"
  [ "$code" = "$4" ] || { err "$1 $2 → HTTP $code (기대 $4)"; exit 1; }
}
call GET  /users/me "$ADMIN_TOKEN" 200                        # 관리자 이메일 → ADMIN 승격
call GET  /users/me "$HOST_TOKEN" 200                         # 최초 로그인 → CUSTOMER 자동 생성
call POST /instructors/apply "$HOST_TOKEN" 200                # 강사 신청 (PENDING)
call POST "/instructors/$HOST_ID/approve" "$ADMIN_TOKEN" 200  # 관리자 승인 (ACTIVE)

log "4) 주요 흐름 실행 (run_flow.sh)"
bash scripts/run_flow.sh

log "ALL OK 🎉"
