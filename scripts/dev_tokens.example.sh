# 사용법:
# 1) 이 파일을 scripts/dev_tokens.sh로 복사
# 2) 값 채우고
# 3) source scripts/dev_tokens.sh

# ====== 고정 ======
export BASE_URL="http://127.0.0.1:8000"

# ====== Supabase ======
export SUPABASE_URL="https://<project_ref>.supabase.co"
export SUPABASE_ANON_KEY=""

# ====== 테스트 계정(로컬 전용) ======
export GUEST_EMAIL="guest@test.com"
export GUEST_PASSWORD=""

export HOST_EMAIL="host@test.com"
export HOST_PASSWORD=""
