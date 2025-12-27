# 사용법:
# 서버 가동 후 테스트 터미널에서 실행
#   source scripts/dev_tokens.sh
#   source scripts/load_tokens.sh << 토큰 만료시 실행
#
# 주의: 토큰/비번은 출력하지 않음 (길이만 출력)

set -euo pipefail

require() {
  if [ -z "${!1:-}" ]; then
    echo "ERROR: env var '$1' is not set" >&2
    return 1
  fi
}

require BASE_URL
require SUPABASE_URL
require SUPABASE_ANON_KEY
require GUEST_EMAIL
require GUEST_PASSWORD
require HOST_EMAIL
require HOST_PASSWORD

get_token() {
  local email="$1"
  local password="$2"

  curl -sS -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_ANON_KEY" \
    -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))"
}

export GUEST_TOKEN="$(get_token "$GUEST_EMAIL" "$GUEST_PASSWORD")"
export HOST_TOKEN="$(get_token "$HOST_EMAIL" "$HOST_PASSWORD")"

if [ -z "$GUEST_TOKEN" ] || [ -z "$HOST_TOKEN" ]; then
  echo "ERROR: token 발급 실패(이메일 인증/비번/anon key 확인 필요)" >&2
  exit 1
fi

# HOST_ID 자동 추출 (백엔드가 켜져 있어야 함)
export HOST_ID="$(
  curl -sS "$BASE_URL/accounts/me" -H "Authorization: Bearer $HOST_TOKEN" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])"
)"

echo "OK:"
echo "  BASE_URL=$BASE_URL"
echo "  GUEST_TOKEN length=${#GUEST_TOKEN}"
echo "  HOST_TOKEN length=${#HOST_TOKEN}"
echo "  HOST_ID=$HOST_ID"
