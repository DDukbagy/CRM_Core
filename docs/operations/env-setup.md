# env 파일 설정과 Codespace 복구

> env 파일에는 실제 비밀값이 들어간다. **값은 이 문서에 쓰지 않는다.** 변수 이름과 어디서 구하는지만 적는다.
> 각 폴더의 `.env.example` 을 복사해 값만 채운다. env 파일은 모두 해당 폴더 `.gitignore` 에 걸린다. 루트에는 env 를 만들지 않는다(어느 코드도 읽지 않음).

## 1. 파일과 변수

### backend/.env

| 변수 | 필수 | 어디서 |
|---|---|---|
| `DATABASE_URL` | **필수** | Supabase → Project Settings → Database → Connection string (**Session pooler**, IPv4. Codespace 는 IPv6 직접 연결 불가) |
| `SUPABASE_URL` | **필수** | Supabase → Project Settings → Data API(또는 API) → Project URL |
| `SUPABASE_ANON_KEY` | **필수** | Project Settings → API Keys → anon / public |
| `SUPABASE_JWT_SECRET` | **필수** | Project Settings → JWT Keys (대시보드 버전에 따라 API → JWT Settings) |
| `SECRET_KEY` | **필수** | 직접 만든 긴 무작위 문자열 (로컬 HS256 폴백 토큰용) |
| `SUPER_ADMIN_EMAIL` 또는 `SUPER_ADMIN_USER_ID` | 첫 관리자 | 이 계정으로 로그인하면 ADMIN 으로 승격 |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `AWS_REGION` | 파일 업로드 | AWS IAM·S3 ([verification.md](verification.md) 6단계) |
| `CORS_ALLOW_ORIGINS`, `CORS_ORIGIN_REGEX` | 선택 | 웹·앱 주소 |
| `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | 선택 | 발급자·대상이 기본값과 다를 때만 |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | 선택 | Sentry |
| `DB_SSL_DISABLE` | 로컬 DB 만 | `1` (원격 Supabase 에는 쓰지 않음) |

테스트(`make apitest`, `make apiverify`)는 이 파일을 쓰지 않는다. `backend/scripts/local_env.sh`(더미 값)와 로컬 Postgres 컨테이너를 쓴다.

### frontend/.env.local

| 변수 | 필수 | 값 |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | **필수** | 위 Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **필수** | 위 anon key |
| `API_BASE_URL` | **필수** | `http://localhost:8000` (웹 서버가 대신 호출) |
| `ENABLE_DEV_BEARER`, `DEV_BEARER_TOKEN` | 개발 전용 | 운영에서는 설정하지 않음 |

### apps/customer/.env, apps/instructor/.env

| 변수 | 필수 | 값 |
|---|---|---|
| `EXPO_PUBLIC_SUPABASE_URL` | **필수** | 위 Project URL |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | **필수** | 위 anon key. ⚠️ service_role·secret key 는 절대 넣지 않음 |
| `EXPO_PUBLIC_API_BASE_URL` | 내 PC 브라우저·실기기 | VS Code 포트 탭의 8000 주소 (Public, 끝 `/` 없이). Codespace 안 브라우저면 생략(기본 `http://localhost:8000`) |
| `EXPO_PUBLIC_APP_ENV`, `EXPO_PUBLIC_SENTRY_DSN` | 선택 | Sentry |

- env 를 바꾸면 `make cweb`·`make iweb` 을 껐다 켠다.
- Expo 우선순위: `.env.local` > `.env`. `.env.local` 이 있으면 그 값을 쓴다.

### apps/.env (실기기 터널, 선택)

| 변수 | 값 |
|---|---|
| `NGROK_AUTHTOKEN` | ngrok 대시보드. `make ctunnel`·`make itunnel` 이 읽음 (각 앱 폴더로 옮길지 결정 대기, progress.md §6) |

### 결제 연동 시 추가 (아직 없음)

[pg-integration.md](pg-integration.md) 3.3 참고.

---

## 2. Codespace 가 새로 만들어졌을 때 복구 순서

1. env 파일 4개 다시 작성 (값은 Supabase 대시보드·AWS·비밀번호 관리자에서). Codespaces Secrets 에 넣어 두면 다음부터 편함
2. `npm ci` — `frontend`, `apps/customer`, `apps/instructor`
3. 백엔드: `cd backend && poetry install`
4. 확인: `make check` (로컬 DB 자동 생성) → `make dbcheck` (원격 DB 연결) → `make migcheck` (원격 ↔ 모델 차이 0)
5. 저장소 밖(필요할 때): `gh auth login`, `aws configure`, `eas login`
