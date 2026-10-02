#!/usr/bin/env bash
# 로컬 검증 전용 설정 — source 해서 쓴다 (backend/.env 값을 이 값으로 덮어쓴다)
# - 모든 값은 로컬 더미 값이며 비밀이 아니다. 원격 DB(Supabase)·AWS 에 절대 연결하지 않는다.
# - 사용처: scripts/local_db.sh, scripts/test_local.sh, scripts/verify.sh
LOCAL_DB_CONTAINER="${LOCAL_DB_CONTAINER:-crm-local-db}"
LOCAL_DB_PORT="${LOCAL_DB_PORT:-55433}"
LOCAL_DB_NAME="${LOCAL_DB_NAME:-crm_local}"

export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${LOCAL_DB_PORT}/${LOCAL_DB_NAME}"
export DB_SSL_DISABLE=1
export DB_ECHO=false

export SUPABASE_URL="http://127.0.0.1:54321"
export SUPABASE_ANON_KEY="local-anon-key"
export SUPABASE_JWT_SECRET="local-supabase-jwt-secret-not-for-production"
export SUPABASE_JWT_AUDIENCE="authenticated"
export SECRET_KEY="local-backend-secret-not-for-production"
export ALGORITHM="HS256"
export SUPER_ADMIN_USER_ID=""
export SUPER_ADMIN_EMAIL="local-admin@example.com"
export SENTRY_DSN=""
export CORS_ALLOW_ORIGINS='["http://localhost:3000"]'
export CORS_ORIGIN_REGEX=""

# S3 는 서명 주소 생성만 로컬에서 동작하고 실제 업로드·삭제는 하지 않는다
export AWS_ACCESS_KEY_ID="local-dummy-access-key"
export AWS_SECRET_ACCESS_KEY="local-dummy-secret-key"
export AWS_REGION="ap-northeast-2"
export S3_BUCKET_NAME="crm-local-dummy-bucket"
