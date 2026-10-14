# 데모 배포 (포트폴리오 미리보기)

> 운영 배포(AWS Copilot)와 별개인 **데모 전용** 환경이다. 데이터·계정·DB 를 개발/운영과 섞지 않는다.
> 값(키·비밀번호·DB 주소)은 이 문서에 쓰지 않는다. 각 서비스 대시보드에만 입력한다.

## 구성

| 대상 | 서비스 | 설정 파일 | 비용 |
|---|---|---|---|
| DB·로그인 | Supabase **데모 전용 새 프로젝트** | — | 무료 (7일 미사용 시 일시 중지 → 대시보드에서 Restore) |
| 백엔드 | Render Web Service (Docker) | `render.yaml` | 무료 (15분 미사용 시 잠듦 → 첫 요청 30초~1분) |
| 관리자·강사 웹 | Vercel (Root Directory `frontend`) | 없음 (Next.js 자동) | 무료 (Hobby) |
| 고객 앱 | Vercel (Root Directory `apps/customer`) | `apps/customer/vercel.json` | 무료 |
| 강사 앱 | Vercel (Root Directory `apps/instructor`) | `apps/instructor/vercel.json` | 무료 |

앱은 `expo export -p web` 정적 사이트로 배포한다. 브라우저에서는 사진 스캔 → PDF, 푸시 알림, 카메라가 동작하지 않는다.

순서가 중요하다: **Supabase → DB 마이그레이션 → Render → Vercel 3개 → CORS → 데모 계정·데이터**

---

## 1. Supabase 데모 프로젝트

1. Supabase 대시보드 → New project (이름 예: `crm-core-demo`, 리전 Seoul)
2. Project Settings 에서 기록 (값은 메모만, 문서·커밋 금지)
   - Project URL, anon key, JWT secret
   - Database → Connection string → **Session pooler** (Render 는 IPv4 라 Direct 연결 불가)
3. Authentication → Sign In / Providers → Email: **Confirm email 끄기** (데모 계정이 바로 로그인되게)

## 2. DB 마이그레이션 (데모 DB 에만)

Codespace 에서 **데모 DB 주소를 명령에만** 넣어 실행한다 (`backend/.env` 는 개발 DB 이므로 바꾸지 않는다).

```bash
cd backend
read -rs DEMO_DB && DATABASE_URL="$DEMO_DB" poetry run alembic upgrade head; unset DEMO_DB
```

- `read -rs` 는 입력이 화면·셸 기록에 남지 않는다. Session pooler 주소를 붙여 넣고 Enter
- 끝나면 같은 방식으로 `alembic current` 가 `z1a2b3c4d5e6 (head)` 인지 확인
- 마지막 마이그레이션(`z1a2b3c4d5e6`)이 웹 로그인에 필요한 `users` 본인 행 읽기 정책을 만든다. SQL 을 따로 실행할 필요 없음

## 3. Render (백엔드)

1. render.com → GitHub 로 가입 → New → **Blueprint** → 저장소 `CRM_Core` 선택 → `render.yaml` 인식
2. `sync: false` 변수 입력

| 변수 | 값 |
|---|---|
| `DATABASE_URL` | 데모 Session pooler 주소 |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` | 데모 프로젝트 값 |
| `SUPER_ADMIN_EMAIL` | 데모 관리자 계정 이메일 (6단계에서 만들 계정) |
| `CORS_ALLOW_ORIGINS` | 일단 비워 두고 5단계에서 채움 |

3. 배포가 끝나면 `https://<서비스 이름>.onrender.com/health` 가 `{"status":"ok"}` 인지 확인

`branch: staging`, `backend/**` 가 바뀔 때만 다시 배포한다.

## 4. Vercel (웹·앱 3개)

vercel.com → GitHub 로 가입 → Add New → Project → `CRM_Core` 를 **세 번** 가져온다. 프로젝트마다 Root Directory 와 Environment Variables 만 다르다. Production Branch 는 `staging`.

| 프로젝트 이름 (예) | Root Directory | Environment Variables |
|---|---|---|
| `crm-core-demo-web` | `frontend` | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `API_BASE_URL` = Render 주소 |
| `crm-core-demo-customer` | `apps/customer` | `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `EXPO_PUBLIC_API_BASE_URL` = Render 주소 |
| `crm-core-demo-instructor` | `apps/instructor` | 고객 앱과 같음 |

- ⚠️ `EXPO_PUBLIC_`·`NEXT_PUBLIC_` 에는 **anon key 만**. service_role key 는 절대 넣지 않는다 (브라우저에 그대로 노출됨)
- `EXPO_PUBLIC_` 값은 빌드할 때 들어간다. 값을 바꾸면 Redeploy
- 앱 두 개는 `vercel.json` 이 빌드 명령(`npx expo export -p web`)·출력 폴더(`dist`)·상세 화면 주소를 정한다

## 5. CORS

앱은 브라우저에서 백엔드를 직접 부른다(웹은 프록시라 필요 없음). Render → Environment → `CORS_ALLOW_ORIGINS` 에 두 앱 주소를 쉼표로:

```
https://crm-core-demo-customer.vercel.app,https://crm-core-demo-instructor.vercel.app
```

저장하면 Render 가 다시 시작한다.

## 6. 데모 계정·데이터

1. Supabase → Authentication → Users → Add user → **Create new user** 로 4개 (같은 비밀번호, Auto Confirm 체크)
   - 관리자 (`SUPER_ADMIN_EMAIL` 과 같은 이메일), 강사, 고객, 고객2
2. Codespace 에서 데모 데이터 넣기 (값은 입력만, 출력 안 됨)

```bash
cd backend
read -rp "데모 API 주소: " DEMO_API_URL; read -rp "Supabase URL: " SUPABASE_URL
read -rsp "anon key: " SUPABASE_ANON_KEY; echo; read -rsp "데모 비밀번호: " DEMO_PASSWORD; echo
read -rp "관리자 이메일: " DEMO_ADMIN_EMAIL; read -rp "강사 이메일: " DEMO_INSTRUCTOR_EMAIL
read -rp "고객 이메일: " DEMO_CUSTOMER_EMAIL; read -rp "고객2 이메일(없으면 Enter): " DEMO_CUSTOMER2_EMAIL
export DEMO_API_URL SUPABASE_URL SUPABASE_ANON_KEY DEMO_PASSWORD DEMO_ADMIN_EMAIL DEMO_INSTRUCTOR_EMAIL DEMO_CUSTOMER_EMAIL DEMO_CUSTOMER2_EMAIL
poetry run python scripts/seed_demo.py
```

`scripts/seed_demo.py` 가 실제 API 로 강사 승인, 프로필, 담당 고객, 수강권·결제, 예약(확정 1·신청 1), 레슨노트, 게시물, 프로모션, 채팅을 만든다. 이미 데이터가 있으면 아무것도 하지 않고 멈춘다.

## 7. README 링크

루트 `README.md` 의 "데모" 표에 Vercel 주소 3개와 데모 계정(이메일, 공용 비밀번호)을 적는다.
데모 비밀번호는 공개되는 값이므로 **다른 곳에서 쓰지 않는 값**으로 만든다.

---

## 확인 목록

- [ ] `/health` 200
- [ ] 웹: 강사 계정 로그인 → `/instructor` 대시보드 (역할 읽기 정책이 없으면 로그인 화면으로 돌아옴: 2단계 마이그레이션 확인)
- [ ] 고객 앱: 로그인 → 홈·달력·수강권(프로모션 표시)·레슨노트·채팅
- [ ] 강사 앱: 로그인 → 대시보드·고객·스케줄·매출 → 운영 현황
- [ ] 브라우저 개발자 도구에 CORS 오류 없음

## 문제가 생기면

| 증상 | 원인·해결 |
|---|---|
| 첫 접속이 오래 걸림 | Render 무료가 잠들어 있음. 30초~1분 뒤 정상 |
| 로그인 후 아무것도 안 나옴 | Supabase 데모 프로젝트 일시 중지 → Restore |
| 앱에서 `Failed to fetch` | `CORS_ALLOW_ORIGINS` 에 앱 주소가 정확한지 (끝 `/` 없이) |
| 웹 로그인 후 다시 로그인 화면 (`ROLE_UNAVAILABLE`) | 마이그레이션이 head(`z1a2b3c4d5e6`)까지 안 됨 → 2단계 다시 |
| 상세 화면 새로고침 시 404 | `vercel.json` 의 rewrites 확인 |
