# 사용법:
#   source scripts/dev_tokens.sh
#   source scripts/load_tokens.sh
#   ./scripts/run_flow.sh
#
# 주의:
# - 이 파일은 "source"로 실행되므로 exit를 쓰면 현재 터미널이 종료됨
# - 그래서 실패 시 return으로 빠져나가고, shell 옵션도 원상복구함

# --- save/restore shell options (source-safe) ---
__OLD_SET_OPTS="$(set +o)"
set -u  # unset 변수 참조 방지 (필요하면 꺼도 됨)

__restore_opts() {
  eval "$__OLD_SET_OPTS"
  unset __OLD_SET_OPTS
}
trap '__restore_opts' RETURN

fail() {
  echo "ERROR: $*" >&2
  return 1
}

require() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    fail "env var '$name' is not set"
  fi
}

get_token() {
  local email="$1"
  local password="$2"

  # curl 실패해도 터미널 죽지 않게 처리 (에러는 메시지로)
  local resp
  resp="$(curl -sS -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_ANON_KEY" \
    -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}" 2>/dev/null || true)"

  # access_token 없으면 에러 JSON일 가능성이 큼
  local token
  token="$(printf '%s' "$resp" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)"

  if [ -z "$token" ]; then
    # 에러 원인 확인을 위해 message만 뽑아봄(없으면 raw 일부 출력)
    local msg
    msg="$(printf '%s' "$resp" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('error_description') or d.get('msg') or d.get('message') or '')" 2>/dev/null || true)"
    if [ -n "$msg" ]; then
      fail "token 발급 실패: $msg"
    else
      fail "token 발급 실패(응답 확인 필요). resp_head=$(printf '%.120s' "$resp")"
    fi
  fi

  printf '%s' "$token"
}

# --- required vars ---
require BASE_URL || return 1
require SUPABASE_URL || return 1
require SUPABASE_ANON_KEY || return 1
require GUEST_EMAIL || return 1
require GUEST_PASSWORD || return 1
require HOST_EMAIL || return 1
require HOST_PASSWORD || return 1

# --- issue tokens ---
export GUEST_TOKEN
GUEST_TOKEN="$(get_token "$GUEST_EMAIL" "$GUEST_PASSWORD")" || return 1

export HOST_TOKEN
HOST_TOKEN="$(get_token "$HOST_EMAIL" "$HOST_PASSWORD")" || return 1

# --- derive HOST_ID from backend (server must be running) ---
export HOST_ID
HOST_ID="$(curl -sS "$BASE_URL/accounts/me" -H "Authorization: Bearer $HOST_TOKEN" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || true)"

if [ -z "$HOST_ID" ]; then
  fail "HOST_ID 추출 실패: 백엔드가 켜져있는지(BASE_URL), HOST_TOKEN이 유효한지 확인"
fi

echo "OK:"
echo "  BASE_URL=$BASE_URL"
echo "  GUEST_TOKEN length=${#GUEST_TOKEN}"
echo "  HOST_TOKEN length=${#HOST_TOKEN}"
echo "  HOST_ID=$HOST_ID"
