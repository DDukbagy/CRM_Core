# 화면 점검 도구 (Playwright)

웹·두 앱을 실제 브라우저로 열어 클릭·입력하고, DB 와 화면 문구로 결과를 확인하는 도구.
외부 서비스 없이 **로컬 Postgres 컨테이너 + 가짜 Supabase(`mock_supabase.py`)** 로 돈다. 원격 DB 에 연결하지 않는다.

> 원래 Codespace 의 `/workspaces/.crm-ui-check` 에 있던 것을 저장소로 옮겼다 (2026-10-25). 경로는 이 폴더 기준으로 찾는다.
> 아직 CI 에는 연결되어 있지 않다 (`docs/launch-readiness.md` B-4).

## 준비 (처음 한 번)

```bash
cd tools/ui-check
npm install
npx playwright install chromium
```

필요: Docker(로컬 DB 컨테이너), `backend/.venv`(`cd backend && poetry install`), 각 앱·웹 `npm install`.

## 실행 순서

```bash
cd tools/ui-check
bash backend.sh                # 로컬 DB(crm_ui) 새로 만들기 → 가짜 Supabase(54321) + 백엔드(8000) → 시드 데이터(ids.json)

bash app.sh web                # 웹을 운영 빌드로 띄움 (3000)   ← 메모리 8GB 기준 한 번에 하나만
node run.mjs web-views         # 화면 열람 (JS 오류·API 4xx/5xx 확인)
node run.mjs web               # 기능 흐름 (레슨노트·프로모션·매출 분석)

bash app.sh customer           # 고객 앱 (8081)
node run.mjs customer-views
node run.mjs customer

bash app.sh instructor         # 강사 앱 (8082)
node run.mjs instructor-views
node run.mjs instructor

bash cleanup.sh                # 서버 끄기 + 임시 .env.local 삭제
```

- `node run.mjs <스위트> <이름 일부>` 로 흐름 하나만 실행할 수 있다
- 결과 스크린샷은 `shots/`, 서버 로그는 `logs/` (둘 다 git 제외)
- 신기능 흐름(`web` → `customer`·`instructor`)은 웹이 만든 데이터를 앱이 확인하므로 **웹을 먼저** 돌린다

## 주의

- `app.sh customer|instructor` 는 앱 폴더에 **임시 `.env.local`**(로컬 더미 값)을 만든다. Expo 는 `.env.local` 을 `.env` 보다 우선하므로, 점검 후 반드시 `cleanup.sh` 로 지운다. 직접 만든 `.env.local` 이 있으면 덮어쓰지 않고 멈춘다
- 데모 사이트 점검(`live.mjs`, `liveweb2.mjs`)은 **배포된 데모**에 실제로 로그인한다 (README 데모 계정). 읽기만 한다

## 파일

| 파일 | 내용 |
|---|---|
| `backend.sh` · `app.sh` · `cleanup.sh` · `killport.sh` | 서버 띄우기·정리 |
| `mock_supabase.py` | 가짜 Supabase Auth (로컬 더미 비밀값으로 토큰 서명) |
| `seed.py` | 점검용 계정·수강권·결제·레슨노트·채팅 → `ids.json` |
| `run.mjs` | 점검 스위트: `web`·`customer`·`instructor`(기능 흐름), `*-views`(화면 열람·다시 들어오기) |
| `live.mjs` · `liveweb2.mjs` | 배포된 데모 로그인·응답 확인 |
| `ci.py` | PR 의 GitHub Actions 결과 확인 (`PR=번호 python3 ci.py`, `GITHUB_TOKEN` 필요) |
| `bench.sh` · `dbping.py` · `dbconn.py` · `stmt_time.py` · `variants.py` · `idle.py` · `drop.py` · `count.py` | 커넥션 풀 성능 측정·실험 (`docs/portfolio/performance-db-connection.md`). 일부는 `backend/.env` 의 개발 DB 에 **읽기 전용**으로 접속 |
| `gzip_upstream.py` | 압축 응답을 흉내 내는 가짜 백엔드 (웹 프록시 결함 재현용) |
| `comments/` | 주석 정리에 쓴 일회성 스크립트 (기록용) |
| 그 외 `*.py` | 일회성 확인 스크립트 (RLS·스키마·게시물 등) |
