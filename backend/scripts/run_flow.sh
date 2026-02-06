#!/usr/bin/env bash
set -u
set -o pipefail

need() {
  local k="$1"
  if [ -z "${!k:-}" ]; then
    echo "ERROR: env var '$k' is not set. 먼저: source scripts/load_tokens.sh" >&2
    exit 1
  fi
}

need BASE_URL
need GUEST_TOKEN
need HOST_TOKEN
need HOST_ID

HTTP_CODE=""
BODY_FILE=""
BODY_BYTES=0

http_json() {
  # usage: http_json METHOD URL [TOKEN] [JSON_DATA]
  local method="$1"
  local url="$2"
  local token="${3:-}"
  local data="${4:-}"

  # 이전 파일 정리
  if [ -n "${BODY_FILE:-}" ] && [ -f "$BODY_FILE" ]; then
    rm -f "$BODY_FILE"
  fi
  BODY_FILE="$(mktemp)"

  local rc=0
  if [ -n "$data" ]; then
    if [ -n "$token" ]; then
      HTTP_CODE="$(curl -sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url" \
        -H "Accept: application/json" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "$data")"; rc=$?
    else
      HTTP_CODE="$(curl -sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url" \
        -H "Accept: application/json" \
        -H "Content-Type: application/json" \
        -d "$data")"; rc=$?
    fi
  else
    if [ -n "$token" ]; then
      HTTP_CODE="$(curl -sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url" \
        -H "Accept: application/json" \
        -H "Authorization: Bearer $token")"; rc=$?
    else
      HTTP_CODE="$(curl -sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url" \
        -H "Accept: application/json")"; rc=$?
    fi
  fi

  BODY_BYTES="$(wc -c < "$BODY_FILE" 2>/dev/null || echo 0)"

  if [ "$rc" -ne 0 ]; then
    echo "❌ curl 실패 rc=$rc method=$method url=$url (http_code=${HTTP_CODE:-?}, bytes=$BODY_BYTES)" >&2
    echo "(body head)" >&2
    head -c 300 "$BODY_FILE" 2>/dev/null || true
    echo >&2
    exit 1
  fi
}

ok_or_die() {
  local step="$1"
  local allow="${2:-}"

  if [[ "${HTTP_CODE:-}" =~ ^2 ]]; then
    echo "✅ $step (HTTP $HTTP_CODE)"
    return 0
  fi
  if [ -n "$allow" ] && [ "$HTTP_CODE" = "$allow" ]; then
    echo "⚠️  $step (HTTP $HTTP_CODE) - 허용된 상태코드"
    return 0
  fi

  echo "❌ $step 실패 (HTTP ${HTTP_CODE:-?}, bytes=$BODY_BYTES)" >&2
  echo "(body head)" >&2
  head -c 400 "$BODY_FILE" 2>/dev/null || true
  echo >&2
  exit 1
}

expect_fail_code_or_die() {
  local step="$1"; shift
  local codes=("$@")

  for c in "${codes[@]}"; do
    if [ "$HTTP_CODE" = "$c" ]; then
      echo "✅ $step (HTTP $HTTP_CODE) - 기대한 실패코드"
      return 0
    fi
  done

  echo "❌ $step 실패: 기대한 실패코드(${codes[*]})가 아님. got=$HTTP_CODE, bytes=$BODY_BYTES" >&2
  echo "(body head)" >&2
  head -c 400 "$BODY_FILE" 2>/dev/null || true
  echo >&2
  exit 1
}

py_pick_timeslot_id_reuse_first() {
  # time_slots 응답: [..] 또는 {"items":[..]} 둘다 처리
  python - "$1" <<'PY'
import sys, json
path=sys.argv[1]
raw=open(path,'rb').read()
# 혹시 모를 NUL 제거(안전)
raw=raw.replace(b'\x00', b'')
text=raw.decode('utf-8','replace').strip()
if not text:
  print(""); raise SystemExit(0)
data=json.loads(text)
items = data.get("items") if isinstance(data, dict) else data
items = items or []
TARGET_START="10:00:00"
TARGET_END="11:00:00"
TARGET_WEEKDAYS=[0,2,4]
def norm(w):
  try: return sorted(int(x) for x in (w or []))
  except: return []
for it in items:
  if it.get("start_time")==TARGET_START and it.get("end_time")==TARGET_END and norm(it.get("weekdays"))==TARGET_WEEKDAYS:
    print(it.get("id")); raise SystemExit(0)
# fallback: reuse first (쌓이지 않게)
print(items[0].get("id") if items else "")
PY
}

py_pick_first_available() {
  python - "$1" <<'PY'
import sys, json
path=sys.argv[1]
raw=open(path,'rb').read().replace(b'\x00', b'')
text=raw.decode('utf-8','replace').strip()
if not text:
  print("__EMPTY__"); raise SystemExit(0)
data=json.loads(text)
for day in data.get("days", []):
  slots=day.get("slots", [])
  if slots:
    print(day["date"], slots[0]["time_slot_id"]); raise SystemExit(0)
print("__NO_SLOT__")
PY
}

py_has_slot_on_date() {
  python - "$1" "$2" "$3" <<'PY'
import sys, json
path=sys.argv[1]; date=sys.argv[2]; slot=int(sys.argv[3])
raw=open(path,'rb').read().replace(b'\x00', b'')
text=raw.decode('utf-8','replace').strip()
data=json.loads(text) if text else {}
for d in data.get("days", []):
  if d.get("date")!=date: 
    continue
  for s in d.get("slots", []):
    if int(s.get("time_slot_id"))==slot:
      print("YES"); raise SystemExit(0)
print("NO")
PY
}

py_get_id() {
  python - "$1" <<'PY'
import sys, json
path=sys.argv[1]
raw=open(path,'rb').read().replace(b'\x00', b'')
text=raw.decode('utf-8','replace').strip()
print(json.loads(text).get("id"))
PY
}

START_DATE="$(date -I)"
END_DATE="$(date -I -d "+14 days" 2>/dev/null || true)"
if [ -z "$END_DATE" ]; then END_DATE="$START_DATE"; fi

echo "=== FLOW TEST START ==="
echo "BASE_URL=$BASE_URL"
echo "HOST_ID=$HOST_ID"
echo "RANGE=$START_DATE .. $END_DATE"
echo

echo "1) /accounts/me (guest)"
http_json GET "$BASE_URL/accounts/me" "$GUEST_TOKEN"
ok_or_die "게스트 토큰 검증"
echo

echo "2) /accounts/me (host)"
http_json GET "$BASE_URL/accounts/me" "$HOST_TOKEN"
ok_or_die "호스트 토큰 검증"
echo

echo "3) /accounts?limit=10&offset=0 (host only)"
http_json GET "$BASE_URL/accounts?limit=10&offset=0" "$HOST_TOKEN"
ok_or_die "호스트 전용 API"
echo

echo "4) POST /calendars/me"
CAL_PAYLOAD='{"topics":["드라이버","아이언","퍼팅"],"description":"레슨 예약 캘린더입니다."}'
http_json POST "$BASE_URL/calendars/me" "$HOST_TOKEN" "$CAL_PAYLOAD"
ok_or_die "캘린더 생성" "409"
echo

echo "5) GET /calendars/me"
http_json GET "$BASE_URL/calendars/me" "$HOST_TOKEN"
ok_or_die "캘린더 조회"
echo

echo "6) GET /calendars/me/time-slots (reuse)"
http_json GET "$BASE_URL/calendars/me/time-slots" "$HOST_TOKEN"
ok_or_die "타임슬롯 목록 조회"
reuse_id="$(py_pick_timeslot_id_reuse_first "$BODY_FILE" || true)"

if [ -n "$reuse_id" ]; then
  TIME_SLOT_ID="$reuse_id"
  echo "✅ 타임슬롯 재사용: TIME_SLOT_ID=$TIME_SLOT_ID"
else
  echo "7) POST /calendars/me/time-slots (create new)"
  TS_PAYLOAD='{"start_time":"10:00:00","end_time":"11:00:00","weekdays":[0,2,4]}'
  http_json POST "$BASE_URL/calendars/me/time-slots" "$HOST_TOKEN" "$TS_PAYLOAD"
  ok_or_die "타임슬롯 생성"
  TIME_SLOT_ID="$(py_get_id "$BODY_FILE")"
  echo "✅ 새 타임슬롯 생성: TIME_SLOT_ID=$TIME_SLOT_ID"
fi
export TIME_SLOT_ID
echo

echo "8) GET /calendars/$HOST_ID/availability (public)"
AV_URL="$BASE_URL/calendars/$HOST_ID/availability?start=$START_DATE&end=$END_DATE"
http_json GET "$AV_URL"
ok_or_die "availability 조회"
echo "   debug: availability bytes=$BODY_BYTES"

pick="$(py_pick_first_available "$BODY_FILE")"
if [ "$pick" = "__EMPTY__" ]; then
  echo "❌ availability 바디가 비어있음(진짜로 파일이 비어있음). bytes=$BODY_BYTES" >&2
  exit 1
elif [ "$pick" = "__NO_SLOT__" ]; then
  echo "❌ 조회 범위에서 예약 가능한 슬롯이 없음(weekday/범위/기존예약 확인 필요)" >&2
  exit 1
fi

BOOK_DATE="$(echo "$pick" | awk '{print $1}')"
BOOK_SLOT_ID="$(echo "$pick" | awk '{print $2}')"
echo "선택된 예약 후보: date=$BOOK_DATE time_slot_id=$BOOK_SLOT_ID"
echo

echo "9) POST /bookings (guest)"
BOOK_PAYLOAD="$(cat <<JSON
{
  "time_slot_id": $BOOK_SLOT_ID,
  "when": "$BOOK_DATE",
  "topic": "[TEST] 아이언",
  "description": null
}
JSON
)"
http_json POST "$BASE_URL/bookings" "$GUEST_TOKEN" "$BOOK_PAYLOAD"
ok_or_die "예약 생성"
BOOKING_ID="$(py_get_id "$BODY_FILE")"
export BOOKING_ID
echo "BOOKING_ID=$BOOKING_ID"
echo

echo "10) 중복 예약 방지 테스트(같은 date/slot 재예약)"
http_json POST "$BASE_URL/bookings" "$GUEST_TOKEN" "$BOOK_PAYLOAD"
expect_fail_code_or_die "중복 예약 방지" "409" "400" "422"
echo

echo "11) availability 재조회(예약 후 슬롯 제거 확인)"
http_json GET "$AV_URL"
ok_or_die "availability 재조회"
present="$(py_has_slot_on_date "$BODY_FILE" "$BOOK_DATE" "$BOOK_SLOT_ID")"
if [ "$present" = "YES" ]; then
  echo "❌ 예약 후에도 슬롯이 남아있음: $BOOK_DATE slot=$BOOK_SLOT_ID" >&2
  exit 1
fi
echo "✅ 예약 후 슬롯 제거 확인 OK"
echo

echo "12) PATCH /bookings/$BOOKING_ID/cancel (guest)"
http_json PATCH "$BASE_URL/bookings/$BOOKING_ID/cancel" "$GUEST_TOKEN"
ok_or_die "게스트 예약 취소"
echo

echo "13) availability 재조회(취소 후 슬롯 복구 확인)"
http_json GET "$AV_URL"
ok_or_die "availability 재조회"
present="$(py_has_slot_on_date "$BODY_FILE" "$BOOK_DATE" "$BOOK_SLOT_ID")"
if [ "$present" != "YES" ]; then
  echo "❌ 취소 후에도 슬롯이 복구되지 않음: $BOOK_DATE slot=$BOOK_SLOT_ID" >&2
  exit 1
fi
echo "✅ 취소 후 슬롯 복구 확인 OK"
echo

echo "14) GET /calendars/me/bookings (host)"
HOST_BOOK_URL="$BASE_URL/calendars/me/bookings?start=$START_DATE&end=$END_DATE"
http_json GET "$HOST_BOOK_URL" "$HOST_TOKEN"
ok_or_die "호스트 예약 목록"
echo

echo "=== FLOW TEST DONE ✅ ==="
echo "used TIME_SLOT_ID=$TIME_SLOT_ID"
echo "selected date=$BOOK_DATE, time_slot_id=$BOOK_SLOT_ID, booking_id=$BOOKING_ID"
