#!/usr/bin/env bash
H="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$H/logs" "$H/shots"; R="$(cd "$H/../.." && pwd)"
bash $H/killport.sh 3000 8000 8081 8082 54321
for a in customer instructor; do grep -q "local-anon-key" $R/apps/$a/.env.local 2>/dev/null && rm $R/apps/$a/.env.local && echo "삭제 apps/$a/.env.local"; done
echo 정리 완료
