#!/usr/bin/env bash
# 부하 테스트 실행: 조건마다 DB 를 같은 더미 데이터로 되돌리고 → 서버를 띄우고 → 사용자 수 단계별로 Locust 를 돌린다
#
# - 로컬 Postgres 컨테이너(crm_load DB)에만 연결한다. backend/.env·원격 DB 는 쓰지 않는다 (scripts/local_env.sh)
# - NET=direct  : 서버 → 로컬 DB 바로
#   NET=latency : 서버 → toxiproxy(왕복 LATENCY_MS) → 로컬 DB. 예전 원격 Supabase 왕복(77ms)을 흉내 낸다
# - POOLS="pool null" : 커넥션 풀 5+5(개선 후) / NullPool(개선 전). loadtest/serve.py 참고
# - 결과: backend/.tmp/loadtest/<NET>-<POOL>-u<사용자 수>_stats.csv (Locust CSV)
#
# 사용: make apiload                       (두 조건 모두, 단계 10 50 100 명 × 2분)
#       make apiload NET=latency STAGES="10" DURATION=30s POOLS=pool   (일부만)
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"
export LOCAL_DB_NAME=crm_load
source scripts/local_env.sh

NETS="${NET:-direct latency}"
POOLS="${POOLS:-pool null}"
STAGES="${STAGES:-10 50 100}"
DURATION="${DURATION:-2m}"
LATENCY_MS="${LATENCY_MS:-77}"
PORT="${LOAD_PORT:-8770}"
PROXY_PORT=55434
OUT="$BACKEND_DIR/.tmp/loadtest"
LOCUST="$BACKEND_DIR/loadtest/.venv/bin/locust"
DIRECT_DB_URL="$DATABASE_URL"
SERVER_PGID=""

log() { echo -e "▶ $*"; }

[ -x "$LOCUST" ] || {
  echo "Locust 가 없습니다: python3 -m venv loadtest/.venv && loadtest/.venv/bin/pip install -r loadtest/requirements.txt" >&2
  exit 1
}

stop_server() {
  # uvicorn 은 종료 신호를 받아도 처리 중인 요청을 끝낼 때까지 돈다. 다 꺼진 뒤에 다음 측정의 DB 를 지운다
  # (꺼지기 전에 지우면 남은 요청이 '테이블 없음' 500 을 낸다). 15초 안에 안 꺼지면 강제로 끈다
  if [ -n "$SERVER_PGID" ]; then
    kill -- "-$SERVER_PGID" >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do
      kill -0 -- "-$SERVER_PGID" >/dev/null 2>&1 || break
      sleep 0.5
    done
    kill -9 -- "-$SERVER_PGID" >/dev/null 2>&1 || true
    SERVER_PGID=""
  fi
}
stop_proxy() { docker rm -f crm-load-proxy >/dev/null 2>&1 || true; }
trap 'stop_server; stop_proxy' EXIT

start_proxy() {
  stop_proxy
  local db_ip
  db_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$LOCAL_DB_CONTAINER")"
  docker run -d --name crm-load-proxy -p 127.0.0.1:8474:8474 -p "127.0.0.1:${PROXY_PORT}:${PROXY_PORT}" \
    ghcr.io/shopify/toxiproxy:2.9.0 >/dev/null
  for _ in $(seq 1 20); do curl -sf -o /dev/null http://127.0.0.1:8474/version && break; sleep 0.5; done
  curl -sf -o /dev/null -X POST http://127.0.0.1:8474/proxies \
    -d "{\"name\":\"pg\",\"listen\":\"0.0.0.0:${PROXY_PORT}\",\"upstream\":\"${db_ip}:5432\"}"
  # 왕복 지연을 반씩 나눠 보내는 쪽·받는 쪽에 건다
  local half=$((LATENCY_MS / 2))
  for stream in upstream downstream; do
    curl -sf -o /dev/null -X POST http://127.0.0.1:8474/proxies/pg/toxics \
      -d "{\"name\":\"lat_${stream}\",\"type\":\"latency\",\"stream\":\"${stream}\",\"attributes\":{\"latency\":${half}}}"
  done
}

mkdir -p "$OUT"
for net in $NETS; do
  if [ "$net" = "latency" ]; then
    start_proxy
    export DATABASE_URL="${DIRECT_DB_URL/:${LOCAL_DB_PORT}\//:${PROXY_PORT}/}"
  else
    stop_proxy
    export DATABASE_URL="$DIRECT_DB_URL"
  fi

  for pool in $POOLS; do
    for users in $STAGES; do
      name="${net}-${pool}-u${users}"
      log "$name: 데이터 되돌리기"
      bash scripts/local_db.sh recreate "$LOCAL_DB_NAME" >/dev/null 2>&1
      DATABASE_URL="$DIRECT_DB_URL" poetry run python loadtest/seed.py >/dev/null

      log "$name: 서버 실행 (POOL=$pool)"
      setsid env POOL="$pool" PORT="$PORT" poetry run python loadtest/serve.py >"$OUT/${name}_server.log" 2>&1 &
      SERVER_PGID="$!"
      for _ in $(seq 1 30); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/db" && break; sleep 1; done
      curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/db" || { echo "서버가 뜨지 않음: $OUT/${name}_server.log" >&2; exit 1; }

      log "$name: Locust ${users}명 × ${DURATION}"
      "$LOCUST" -f loadtest/locustfile.py --headless --host "http://127.0.0.1:$PORT" \
        -u "$users" -r "$users" -t "$DURATION" --csv "$OUT/$name" --only-summary >"$OUT/${name}_locust.log" 2>&1 || true
      stop_server
    done
  done
done

log "끝. 요약: poetry run python loadtest/report.py"
