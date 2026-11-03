#!/usr/bin/env bash
# 앱 하나만 실행 (메모리 8GB): app.sh customer|instructor|web   — 실행 중인 다른 클라이언트는 끈다
H="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$H/logs" "$H/shots"; R="$(cd "$H/../.." && pwd)"
bash $H/killport.sh 3000 8081 8082; sleep 1
export CI=1 BROWSER=none EXPO_NO_TELEMETRY=1 NEXT_TELEMETRY_DISABLED=1
case "$1" in
  web)
    cd $R/frontend
    export NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 NEXT_PUBLIC_SUPABASE_ANON_KEY=local-anon-key API_BASE_URL=http://127.0.0.1:8000
    npx next build > $H/logs/web-build.log 2>&1 || { echo "web build 실패"; tail -20 $H/logs/web-build.log; exit 1; }
    (setsid npx next start -p 3000 > $H/logs/web.log 2>&1 &); URL=http://127.0.0.1:3000/login ;;
  customer|instructor)
    port=$([ "$1" = customer ] && echo 8081 || echo 8082)
    # 사용자의 .env 보다 우선하는 임시 .env.local (로컬 더미 값, git 무시). 끝나면 cleanup.sh 로 삭제
    if [ -f "$R/apps/$1/.env.local" ] && ! grep -q "local-anon-key" "$R/apps/$1/.env.local"; then echo "apps/$1/.env.local 이 이미 있음 (직접 만든 파일) → 덮어쓰지 않고 중단"; exit 1; fi
    printf 'EXPO_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321\nEXPO_PUBLIC_SUPABASE_ANON_KEY=local-anon-key\nEXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000\nEXPO_PUBLIC_APP_ENV=local\nEXPO_PUBLIC_SENTRY_DSN=\n' > $R/apps/$1/.env.local
    cd $R/apps/$1 && (setsid npx expo start --web --port $port --clear > $H/logs/$1.log 2>&1 &); URL=http://127.0.0.1:$port/ ;;
esac
for i in $(seq 1 150); do curl -s -o /dev/null -m 120 $URL && break; sleep 2; done
echo "$1 실행"
