#!/usr/bin/env bash
# 로컬 Postgres(Docker) 관리
#   up              컨테이너 시작 (없으면 생성)
#   down            컨테이너 중지
#   recreate <db>   DB를 지우고 빈 DB로 다시 만든 뒤 alembic upgrade head
set -euo pipefail
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$BACKEND_DIR/scripts/local_env.sh"

psql_admin() { docker exec "$LOCAL_DB_CONTAINER" psql -U postgres -qAt "$@"; }

up() {
  if ! docker ps -a --format '{{.Names}}' | grep -qx "$LOCAL_DB_CONTAINER"; then
    echo "▶ 로컬 DB 컨테이너 생성: $LOCAL_DB_CONTAINER (127.0.0.1:$LOCAL_DB_PORT)"
    docker run -d --name "$LOCAL_DB_CONTAINER" \
      -e POSTGRES_PASSWORD=postgres -p "127.0.0.1:${LOCAL_DB_PORT}:5432" postgres:16 >/dev/null
  elif [ "$(docker inspect -f '{{.State.Running}}' "$LOCAL_DB_CONTAINER")" != "true" ]; then
    echo "▶ 로컬 DB 컨테이너 시작: $LOCAL_DB_CONTAINER"
    docker start "$LOCAL_DB_CONTAINER" >/dev/null
  fi
  for _ in $(seq 1 30); do
    if docker exec "$LOCAL_DB_CONTAINER" pg_isready -U postgres -q 2>/dev/null && psql_admin -c "select 1" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "❌ 로컬 DB가 30초 안에 준비되지 않았습니다." >&2
  exit 1
}

recreate() {
  local db="${1:?DB 이름이 필요합니다}"
  up
  psql_admin -c "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" -c "CREATE DATABASE \"$db\""
  (cd "$BACKEND_DIR" && LOCAL_DB_NAME="$db" bash -c 'source scripts/local_env.sh && poetry run alembic upgrade head' >/dev/null)
  echo "✅ 로컬 DB $db 준비 완료 (마이그레이션 head)"
}

case "${1:-up}" in
  up) up; echo "✅ 로컬 DB 실행 중: 127.0.0.1:$LOCAL_DB_PORT (컨테이너 $LOCAL_DB_CONTAINER)" ;;
  down) docker stop "$LOCAL_DB_CONTAINER" >/dev/null 2>&1 || true; echo "⏹  로컬 DB 중지" ;;
  recreate) recreate "${2:-}" ;;
  *) echo "사용법: $0 up | down | recreate <db>" >&2; exit 1 ;;
esac
