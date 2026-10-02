#!/usr/bin/env bash
# 백엔드 테스트를 로컬 DB로 실행한다 (원격 DB에 연결하지 않음)
#   1) 로컬 DB 컨테이너 준비 → crm_test DB를 새로 만들고 마이그레이션 적용
#   2) alembic check (모델 ↔ DB 일치 확인)
#   3) pytest (인자는 그대로 전달: 예) scripts/test_local.sh -k calendar)
set -euo pipefail
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"
export LOCAL_DB_NAME=crm_test
source scripts/local_env.sh

bash scripts/local_db.sh recreate "$LOCAL_DB_NAME"
echo "▶ alembic check"
poetry run alembic check
echo "▶ pytest"
poetry run pytest "$@"
