#!/usr/bin/env bash
# 원격 DB 로 백엔드를 8011 에 띄우고 실제 API 응답 시간 측정: bench.sh <라벨>
H="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$H/logs" "$H/shots"; R="$(cd "$H/../.." && pwd)"; HID=$(cat $H/hid.txt); S=$(date +%F); E=$(date -d "+6 days" +%F)
bash $H/killport.sh 8011; cd $R/backend
(env -u DATABASE_URL -u DB_SSL_DISABLE setsid poetry run uvicorn app.main:app --host 127.0.0.1 --port 8011 > $H/logs/bench.log 2>&1 &)
for i in $(seq 1 40); do curl -s -o /dev/null http://127.0.0.1:8011/health && break; sleep 1; done
URL="http://127.0.0.1:8011/calendars/$HID/availability?start=$S&end=$E"
echo "== $1: 순차 10회"
for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code} %{time_total}\n" "$URL"; done > $H/logs/seq.txt
python3 - $H/logs/seq.txt <<'PY'
import sys
rows=[l.split() for l in open(sys.argv[1]) if l.strip()]
t=[float(x[1])*1000 for x in rows]; codes={c for c,_ in rows}
print(f"  첫 요청 {t[0]:.0f}ms / 이후 평균 {sum(t[1:])/len(t[1:]):.0f}ms / 전체 평균 {sum(t)/len(t):.0f}ms (상태 {','.join(sorted(codes))})")
PY
echo "== $1: 동시 4개 (화면 하나가 API 여러 개를 동시에 부르는 상황)"
for k in 1 2 3; do
  st=$(date +%s%N); for i in 1 2 3 4; do curl -s -o /dev/null "$URL" & done; wait; en=$(date +%s%N)
  echo "  $(( (en-st)/1000000 ))ms"
done
bash $H/killport.sh 8011
