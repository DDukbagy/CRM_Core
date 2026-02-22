#!/usr/bin/env bash
set -euo pipefail

# Smoke test: Booking flow (create -> confirm -> cancel) + decline flow
# - 로컬: interactive
# - CI: CUSTOMER_EMAIL / CUSTOMER_PASSWORD / INSTRUCTOR_EMAIL / INSTRUCTOR_PASSWORD env로 non-interactive 실행 가능

: "${API_URL:?API_URL is required (e.g. https://xxx.onrender.com/api)}"
: "${SUPABASE_URL:?SUPABASE_URL is required}"
: "${SUPABASE_ANON_KEY:?SUPABASE_ANON_KEY is required}"

TYPE=LESSON
TIME_SLOT_ID="${TIME_SLOT_ID:-1}" # existing slot id used in your environment

get_token() {
  local email="$1"
  local password="$2"
  python - <<PY
import os, requests, json, sys
url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/token?grant_type=password"
headers = {"apikey": os.environ["SUPABASE_ANON_KEY"], "Content-Type":"application/json"}
data = {"email": sys.argv[1], "password": sys.argv[2]}
r = requests.post(url, headers=headers, data=json.dumps(data))
print(r.status_code)
print(r.text)
PY
}

echo "== 입력: CUSTOMER 계정 =="
# CI에서는 CUSTOMER_EMAIL / CUSTOMER_PASSWORD로 넘길 수 있음 (로컬은 interactive)
C_EMAIL="${C_EMAIL:-${CUSTOMER_EMAIL:-}}"
C_PW="${C_PW:-${CUSTOMER_PASSWORD:-}}"
if [[ -z "${C_EMAIL:-}" ]]; then
  read -r -p "Customer email: " C_EMAIL
fi
if [[ -z "${C_PW:-}" ]]; then
  read -r -s -p "Customer password: " C_PW; echo
else
  echo
fi

echo "== 입력: INSTRUCTOR 계정 =="
# CI에서는 INSTRUCTOR_EMAIL / INSTRUCTOR_PASSWORD로 넘길 수 있음 (로컬은 interactive)
I_EMAIL="${I_EMAIL:-${INSTRUCTOR_EMAIL:-}}"
I_PW="${I_PW:-${INSTRUCTOR_PASSWORD:-}}"
if [[ -z "${I_EMAIL:-}" ]]; then
  read -r -p "Instructor email: " I_EMAIL
fi
if [[ -z "${I_PW:-}" ]]; then
  read -r -s -p "Instructor password: " I_PW; echo
else
  echo
fi

echo "== 토큰 발급 =="
c_out=$(get_token "$C_EMAIL" "$C_PW")
c_code=$(echo "$c_out" | head -n1)
c_body=$(echo "$c_out" | tail -n +2)
if [[ "$c_code" != "200" ]]; then
  echo "[ERR] Customer token failed ($c_code): $c_body"
  exit 1
fi
CUSTOMER_TOKEN=$(echo "$c_body" | jq -r '.access_token')

i_out=$(get_token "$I_EMAIL" "$I_PW")
i_code=$(echo "$i_out" | head -n1)
i_body=$(echo "$i_out" | tail -n +2)
if [[ "$i_code" != "200" ]]; then
  echo "[ERR] Instructor token failed ($i_code): $i_body"
  exit 1
fi
INSTRUCTOR_TOKEN=$(echo "$i_body" | jq -r '.access_token')

create_booking() {
  local when="$1"
  curl -sS -w "\n%{http_code}" -X POST "$API_URL/bookings" \
    -H "Authorization: Bearer $CUSTOMER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"time_slot_id\": $TIME_SLOT_ID, \"when\": \"$when\", \"topic\": \"smoke\", \"description\": \"\", \"type\": \"$TYPE\"}"
}

confirm_booking() {
  local booking_id="$1"
  curl -sS -w "\n%{http_code}" -X PATCH "$API_URL/calendars/me/bookings/$booking_id/confirm" \
    -H "Authorization: Bearer $INSTRUCTOR_TOKEN"
}

decline_booking() {
  local booking_id="$1"
  curl -sS -w "\n%{http_code}" -X PATCH "$API_URL/calendars/me/bookings/$booking_id/decline" \
    -H "Authorization: Bearer $INSTRUCTOR_TOKEN"
}

cancel_booking_guest() {
  local booking_id="$1"
  # cleanup reason을 넣어서 확인
  curl -sS -w "\n%{http_code}" -X PATCH "$API_URL/bookings/$booking_id/cancel" \
    -H "Authorization: Bearer $CUSTOMER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"reason":"smoke cleanup"}'
}

# 예약 가능한 날짜 찾기 (최대 30일)
echo "== (1) create booking request =="
BOOKING_ID=""
for i in $(seq 0 30); do
  when=$(date -u -d "+$i day" +%Y-%m-%d 2>/dev/null || date -v+${i}d +%F)
  out="$(create_booking "$when")" || true
  body="$(echo "$out" | head -n -1)"
  code="$(echo "$out" | tail -n 1)"

  if [[ "$code" == "201" ]]; then
    BOOKING_ID=$(echo "$body" | jq -r '.id')
    echo "[OK] created booking_id=$BOOKING_ID when=$when"
    break
  fi

  # not available / conflict면 다음 날짜
  if echo "$body" | jq -e '.detail | contains("Selected date is not available")' >/dev/null 2>&1; then
    continue
  fi
  if echo "$body" | jq -e '.detail.error == "SLOT_ALREADY_BOOKED"' >/dev/null 2>&1; then
    continue
  fi

  echo "[ERR] create failed (code=$code): $body"
  exit 1
done

if [[ -z "$BOOKING_ID" ]]; then
  echo "[ERR] could not create booking within 30 days"
  exit 1
fi

echo "== (2) confirm booking =="
out="$(confirm_booking "$BOOKING_ID")"
body="$(echo "$out" | head -n -1)"
code="$(echo "$out" | tail -n 1)"
if [[ "$code" != "200" ]]; then
  echo "[ERR] confirm failed (code=$code): $body"
  exit 1
fi
echo "$body" | jq .

# cancel (confirm된 booking 취소)
echo "== (2.5) cancel test (confirmed booking) =="
outc="$(cancel_booking_guest "$BOOKING_ID")"
bodyc="$(echo "$outc" | head -n -1)"
codec="$(echo "$outc" | tail -n 1)"
if [[ "$codec" != "200" ]]; then
  echo "[ERR] cancel failed (code=$codec): $bodyc"
  exit 1
fi
echo "$bodyc" | jq .

echo "== (3) decline test (new booking) =="
# decline 테스트용으로 booking 하나 더 생성
BOOKING_ID2=""
for i in $(seq 0 30); do
  when=$(date -u -d "+$i day" +%Y-%m-%d 2>/dev/null || date -v+${i}d +%F)
  out="$(create_booking "$when")" || true
  body="$(echo "$out" | head -n -1)"
  code="$(echo "$out" | tail -n 1)"

  if [[ "$code" == "201" ]]; then
    BOOKING_ID2=$(echo "$body" | jq -r '.id')
    echo "[OK] created booking_id=$BOOKING_ID2 when=$when"
    break
  fi

  if echo "$body" | jq -e '.detail | contains("Selected date is not available")' >/dev/null 2>&1; then
    continue
  fi
  if echo "$body" | jq -e '.detail.error == "SLOT_ALREADY_BOOKED"' >/dev/null 2>&1; then
    continue
  fi
done

if [[ -z "$BOOKING_ID2" ]]; then
  echo "[ERR] could not create booking2 within 30 days"
  exit 1
fi

out="$(decline_booking "$BOOKING_ID2")"
body="$(echo "$out" | head -n -1)"
code="$(echo "$out" | tail -n 1)"
if [[ "$code" != "200" ]]; then
  echo "[ERR] decline failed (code=$code): $body"
  exit 1
fi
echo "$body" | jq .

echo "✅ smoke-booking OK"