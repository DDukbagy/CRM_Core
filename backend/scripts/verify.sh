#!/usr/bin/env bash
set -euo pipefail

# ====== 설정(필요하면 실행 시 환경변수로 덮어쓰기 가능) ======
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PORT="${PORT:-8000}"

# 기본: 서버 유지(verify가 켠 서버도 안 끔)
KEEP_SERVER="${KEEP_SERVER:-1}"

# 건강 체크 후보(네 프로젝트에 /health 없으니 openapi/docs 위주로)
HEALTH_PATHS_DEFAULT=("/health/db")
HEALTH_PATHS=("${HEALTH_PATHS[@]:-${HEALTH_PATHS_DEFAULT[@]}}")

# 엔트리포인트 후보(자동탐지 실패 시 이 후보들로 시도)
APP_IMPORT_CANDIDATES_DEFAULT=("app.main:app" "main:app" "app.api:app" "app.app:app")
APP_IMPORT_CANDIDATES=("${APP_IMPORT_CANDIDATES[@]:-${APP_IMPORT_CANDIDATES_DEFAULT[@]}}")

APP_IMPORT_DEFAULT="app.main:app"
APP_IMPORT="${APP_IMPORT:-$APP_IMPORT_DEFAULT}"

SERVER_CMD_DEFAULT=("poetry" "run" "uvicorn" "$APP_IMPORT" "--reload" "--host" "0.0.0.0" "--port" "$PORT")
SERVER_CMD=("${SERVER_CMD[@]:-${SERVER_CMD_DEFAULT[@]}}")

# ====== 내부 ======
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SERVER_STARTED_BY_VERIFY=0
SERVER_PID=""

log()  { echo -e "✅ $*"; }
warn() { echo -e "⚠️  $*" >&2; }
err()  { echo -e "❌ $*" >&2; }

port_listening() {
  # 포트가 열려 있으면 서버가 살아있다고 판단(헬스 404여도 OK)
  python - <<PY >/dev/null 2>&1
import socket
s=socket.socket()
s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", int("${PORT}")))
    print("open")
except Exception:
    raise SystemExit(1)
finally:
    s.close()
PY
}

http_alive() {
  # 후보 경로들 중 하나라도 "응답을 주면" 살아있다고 판단 (404만 피함)
  local path code
  for path in "${HEALTH_PATHS[@]}"; do
    code="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}${path}" || true)"
    # code=000은 연결 실패
    if [ "$code" != "000" ] && [ "$code" != "404" ]; then
      return 0
    fi
    # 200/301/307/401/403 등은 살아있음(권한 문제여도 서버는 응답)
  done
  return 1
}

server_running() {
  # 포트가 안 열려있으면 서버 없음
  if ! port_listening; then
    return 1
  fi

  # 포트는 열려있는데 health가 안 되면 "다른 프로세스"일 수 있으니 실패 처리
  if http_alive; then
    return 0
  fi

  err "포트 $PORT 는 열려있지만 ${HEALTH_PATHS[*]} 가 정상 응답이 아님. 다른 프로세스가 $PORT 를 쓰는지 또는 HEALTH_PATHS 경로가 맞는지 확인해줘."
  return 1
}

detect_app_import() {
  # APP_IMPORT이 이미 지정되면 그대로 사용
  if [ -n "$APP_IMPORT" ]; then
    echo "$APP_IMPORT"
    return 0
  fi

  # 후보들 중 FastAPI app이 실제로 import되는 걸 찾음
  for cand in "${APP_IMPORT_CANDIDATES[@]}"; do
    if poetry run python - <<PY >/dev/null 2>&1
import importlib
mod, attr = "${cand}".split(":")
m = importlib.import_module(mod)
obj = getattr(m, attr, None)
# FastAPI 인스턴스면 __class__.__name__ == "FastAPI"
assert obj is not None
assert obj.__class__.__name__ == "FastAPI"
PY
    then
      echo "$cand"
      return 0
    fi
  done

  return 1
}

start_server() {
  mkdir -p "$REPO_ROOT/.tmp"
  local logfile="$REPO_ROOT/.tmp/verify_server.log"

  local app_import
  app_import="$(detect_app_import)" || {
    err "FastAPI 엔트리포인트를 자동탐지 못 했어. APP_IMPORT 또는 SERVER_CMD로 지정해줘."
    err "예) APP_IMPORT=\"app.main:app\" ./scripts/verify.sh"
    err "예) SERVER_CMD=(poetry run uvicorn app.main:app --host 127.0.0.1 --port $PORT) ./scripts/verify.sh"
    return 1
  }

  local cmd=()
  if [ "${#SERVER_CMD[@]}" -gt 0 ]; then
    cmd=("${SERVER_CMD[@]}")
  else
    cmd=("poetry" "run" "uvicorn" "$app_import" "--host" "127.0.0.1" "--port" "$PORT")
  fi

  log "백엔드가 안 떠있어서 자동 실행: ${cmd[*]}"
  (cd "$REPO_ROOT" && "${cmd[@]}" >"$logfile" 2>&1) &
  SERVER_PID="$!"
  SERVER_STARTED_BY_VERIFY=1

  # 준비 대기(최대 30초)
  local i
  for i in {1..30}; do
    if server_running; then
      log "백엔드 준비 완료 (pid=$SERVER_PID, url=$BASE_URL)"
      return 0
    fi
    sleep 1
  done

  err "백엔드가 30초 내에 준비되지 않았어. 로그 확인: $logfile"
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  return 1
}

cleanup() {
  # 기본은 KEEP_SERVER=1이라 종료 안 함
  if [ "$KEEP_SERVER" = "1" ]; then
    return 0
  fi
  # verify가 켠 서버만 종료
  if [ "$SERVER_STARTED_BY_VERIFY" = "1" ] && [ -n "$SERVER_PID" ]; then
    log "verify가 켠 서버 종료 (pid=$SERVER_PID)"
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

main() {
  cd "$REPO_ROOT"

  log "1) 인터프리터/의존성 간단 체크"
  poetry run python -c "import fastapi, pydantic; print('imports OK')" >/dev/null

  log "2) 백엔드 상태 확인"
  if server_running; then
    log "백엔드가 이미 켜져있어. 그대로 진행 (url=$BASE_URL)"
  else
    start_server
  fi

  log "3) 토큰 발급"
  source scripts/dev_tokens.sh
  source scripts/load_tokens.sh

  log "4) 플로우 실행"
  ./scripts/run_flow.sh

  log "ALL OK 🎉"
}

main "$@"
