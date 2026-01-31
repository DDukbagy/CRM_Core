#!/bin/bash
set -e

# 1. .env 파일에서 설정값 자동 로드 (URL, KEY)
if [ -f .env ]; then
  # 주석(#) 제외하고 변수 로드
  export $(grep -v '^#' .env | xargs)
fi

# 2. 필수 환경변수 체크 (없으면 물어봄 - 안전장치)
if [ -z "${SUPABASE_URL:-}" ]; then
  read -r -p "🌍 SUPABASE_URL 입력: " SUPABASE_URL
fi
if [ -z "${SUPABASE_ANON_KEY:-}" ]; then
  read -r -s -p "🔑 SUPABASE_ANON_KEY 입력: " SUPABASE_ANON_KEY; echo
fi

echo "--------------------------------------------------------"
echo "✅ 연결 대상: $SUPABASE_URL"
echo "--------------------------------------------------------"

# 3. 사용자 입력 (Email / Password)
# 인자로 받거나, 없으면 물어봄
EMAIL="${1:-}"
if [ -z "$EMAIL" ]; then
  read -r -p "👤 Email: " EMAIL
fi

PASSWORD="${2:-}"
if [ -z "$PASSWORD" ]; then
  read -r -s -p "🔒 Password: " PASSWORD; echo
fi

echo "🔄 토큰 발급 요청 중..."

# 4. Supabase Auth API 호출
RESPONSE=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password"   -H "apikey: $SUPABASE_ANON_KEY"   -H "Authorization: Bearer $SUPABASE_ANON_KEY"   -H "Content-Type: application/json"   -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

# 5. 결과 파싱 (Python 사용 - Access Token & User ID 추출)
# 성공 여부 체크
ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_description', ''))" 2>/dev/null || true)

if [ -n "$ERROR_MSG" ]; then
  echo ""
  echo "❌ 로그인 실패!"
  echo "이유: $ERROR_MSG"
  exit 1
fi

# 토큰 추출
ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
USER_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('id', 'Unknown'))")

# 6. 결과 출력
echo ""
echo "✅ 로그인 성공! (User ID: $USER_ID)"
echo "👇 아래 토큰을 복사해서 Swagger/Postman에 사용하세요 👇"
echo "----------------------------------------------------------------------"
echo "$ACCESS_TOKEN"
echo "----------------------------------------------------------------------"
