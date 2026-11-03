# 출시 준비: 해야 할 일과 개선할 문제

> 2026-10-14 저장소 점검 기준. 진행 상황은 [progress.md](progress.md), 데모 배포는 [operations/demo-deploy.md](operations/demo-deploy.md).
> 법적 요건은 일반 기준이므로 출시 전 전문가·공식 안내로 확인한다.

- **A. 출시 전에 해야 할 일**: 기능·운영 인프라·스토어
- **B. 프로그램상 개선할 문제**: 결함, 코드 품질, 테스트, 정리할 것

---

## A. 출시 전에 해야 할 일

> 2026-10-14 저장소 점검 기준. 법적 요건은 일반 기준이므로 출시 전 전문가·공식 안내로 확인.

### A-1. 🔴 출시 전 필수
| # | 할 일 | 현재 상태 |
|---|---|---|
| 1 | **회원가입·비밀번호 찾기** (고객 앱·강사 앱, 필요 시 웹) | ❌ 없음. 지금은 Supabase 대시보드에서 만든 계정으로만 로그인 |
| 2 | **이용약관·개인정보처리방침** 페이지 + 가입 시 동의(필수·선택 구분) | ❌ 없음. 앱 스토어 심사에도 개인정보처리방침 주소 필요 |
| 3 | **관리자 화면: 강사 승인·회원 관리** | API 만 있음. 운영 방식(강사 신청 vs 합의 후 생성) 결정 먼저 (progress.md §5) |
| 4 | **운영 인프라** (아래 표) | 데모만 있음 |
| 5 | **결제 범위 결정**: 앱 결제 포함 → PG 연동 필수(사업자등록·통신판매업 신고). 현장 결제 + 수동 기록으로 시작 → 결제 버튼 문구 정리 | 수강권 "결제하기" = "결제 준비 중" 안내 |
| 6 | **남은 결함·직접 테스트**: 웹 "💬 피드백" 버튼(400), 실기기(푸시·사진 스캔 → PDF·카메라), S3 업로드 | progress.md §4·§5 |

**운영 인프라 세부**
| 항목 | 할 일 |
|---|---|
| 운영 Supabase | 새 프로젝트(유료 플랜 권장: 일시 중지 없음·백업), 이메일 인증 켜기, 마이그레이션 head 적용(승인 후, `z1a2b3c4d5e6` 포함) |
| 백엔드 (AWS Copilot) | prod 재가동. `backend/copilot/api/manifest.yml` 의 `SUPABASE_URL` 이 **지금 개발 프로젝트를 가리킴** → 운영 값으로. 비밀값은 SSM 에 먼저 등록. CORS 를 운영 도메인으로 |
| 웹 (Vercel, 기존 비데모 프로젝트) | 운영 환경변수, 운영 도메인, Branch Tracking = `main` |
| S3 | 운영 버킷·권한 |
| 모니터링 | Sentry DSN (백엔드·앱), 오류 알림 |
| 반영 | staging → main Release PR(`make gitpr`) → **실제 인프라 smoke test 1회** |

**AWS 설정 상세** (`backend/copilot/`, `.github/workflows/deploy-*.yml`, [operations/aws.md](operations/aws.md) 기준)

| 영역 | 설정할 것 | 현재 상태 / 주의 |
|---|---|---|
| 계정·권한 | AWS 계정, 결제 수단, **예산 알림(AWS Budgets)** | 비용 때문에 중단했던 이력 → 월 예산 알림 먼저 |
| GitHub → AWS | IAM OIDC 역할 2개 + GitHub Secrets `AWS_ROLE_ARN_STAGING`·`AWS_ROLE_ARN_PROD` | 워크플로가 이 역할로 `copilot svc deploy` 실행. 역할 신뢰 정책(저장소·브랜치 제한) 확인 |
| GitHub Environment | `prod` 환경 보호 규칙 (승인자 지정) | `deploy-prod.yml` 이 `environment: prod` 사용, `main` push 때 실행 |
| Copilot 앱·환경 | 앱 이름, `staging`·`prod` 환경 (`copilot env init`/`env deploy`), 리전 `ap-northeast-2` | 환경 manifest 는 `container_insights: false` 만 있음 |
| 서비스 `api` | Load Balanced Web Service, 포트 8080, 헬스체크 `/health/ready`, CPU 256·메모리 512MB·1개 | 운영 트래픽에 맞춰 크기·개수·오토스케일 검토 |
| 비밀값 (SSM, 환경별) | `DATABASE_URL`(운영 Supabase Session pooler), `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `SECRET_KEY`, `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `copilot secret init` 으로 **배포 전에** 등록. 없으면 배포 실패 |
| 일반 변수 (`manifest.yml` `variables:`) | `SUPABASE_URL`, `AWS_REGION`, `CORS_ALLOW_ORIGINS` | ⚠️ `SUPABASE_URL` 이 **개발 프로젝트** → 운영 값. ⚠️ CORS 에 `localhost` 3개 포함 → 운영에서 제거. 환경별로 다르게 하려면 `environments:` 덮어쓰기 사용 |
| **manifest 에 빠진 변수** | `SUPER_ADMIN_EMAIL`(또는 `SUPER_ADMIN_USER_ID`) — 첫 관리자, `SENTRY_DSN`·`SENTRY_ENVIRONMENT=prod` | 없으면 관리자 계정이 생기지 않고, 오류 추적이 안 됨 |
| S3 (addon `crm-videos.yml`) | 환경별 버킷(암호화·버전 관리), 태스크 IAM 정책(Get/Put/Delete) | addon 이 태스크 역할 권한을 주므로 **IAM 액세스 키 비밀값은 없어도 될 수 있음** → 키 대신 역할만 쓰는 쪽으로 정리 검토. 버킷 공개 차단·CORS(앱 직접 업로드) 확인 |
| 도메인·HTTPS | 운영 도메인(예: CORS 에 있는 `albatro.site`), Route 53 + ACM 인증서, `http.alias` | ❌ manifest 에 alias·인증서 설정 없음 → 지금은 ALB 기본 주소만 |
| 모니터링 | CloudWatch 로그(`make prodlogs`), 알람(ALB 5xx·지연, `make prodalarm` 로 이름 확인), Sentry | 알람·알림 대상(이메일·Slack) 설정 필요 |
| 배포 후 확인 | `make prodstatus`, `/health/ready`, 실제 로그인·예약 흐름 smoke test | CLAUDE.md: prod 반영 전 실제 인프라 smoke test 1회 필수 |

**AWS 배포 때 자동으로 되지 않는 것** (직접 해야 함)
- **DB 마이그레이션**: 배포 워크플로·Copilot·Dockerfile 어디에도 `alembic upgrade` 없음 (의도된 것: 원격 DB 는 승인 후 적용). 필요하면 나중에 "승인 버튼" 마이그레이션 단계 추가 검토
- **비밀 환경변수**: `manifest.yml` 의 `secrets:` 는 SSM 값을 읽기만 함 → 배포 전 `copilot secret init` 으로 등록 (없으면 배포 실패)
- 일반 환경변수는 `manifest.yml` 의 `variables:` 에 추가·커밋하면 배포 때 반영

### A-2. 🟡 앱 스토어 출시 (설치형 앱)
- 개발자 계정: Apple(연 유료), Google Play(1회 유료)
- EAS 빌드·제출: `eas.json` 있음, 번들 ID `com.albatro.customer` · `com.albatro.instructor`
- 스토어 정보: 아이콘·스크린샷·설명·개인정보 수집 항목 표시
- 푸시: iOS APNs, Android FCM
- 계정 삭제 기능: ✅ 있음 (회원 탈퇴)

### A-3. 🟢 출시 직후 가능
화면 경미 항목, 큰 화면 파일 분리, lint 경고, `packages/api` 통합, 백업 복구 연습, 결제 상태 변경(환불) 화면, 강사 스태프 관리, 모임 찾기, 프로모션 정식화

---

## B. 프로그램상 개선할 문제

### B-1. 🔴 동작 결함 (사용자가 겪는 오류)
| # | 문제 | 위치 | 해결 방향 |
|---|---|---|---|
| 1 | 강사 웹 게시물의 "💬 피드백" 작성 → 백엔드 400 ("피드백은 레슨노트로 작성합니다") | `frontend/src/app/(protected)/instructor/posts/page.tsx` | 강사 앱처럼 버튼 제거 (UI 변경이라 결정 필요) |
| 2 | 게시물 작성 응답이 502 로 돌아온 적 있음 (저장은 됨, 데모 Render) | 백엔드 `POST /posts` | 원인 미확인. 재현되면 Render·CloudWatch 로그 확인 (재시작 겹침 또는 처리 지연) |
| 3 | 로그인 전 홈이 API 를 먼저 불러 401 로그가 남음 | 앱 홈 화면 (로그인 전) | 로그인 확인 후 호출 |

### B-2. 🟡 화면 다듬기
| # | 문제 | 위치 |
|---|---|---|
| 1 | 영어 원문 그대로 표시 (`COMPLETED`, `MALE` 등) | 강사 앱 |
| 2 | 예약 목록 상단 제목이 `bookings` | 고객 앱 |
| 3 | 웹 왼쪽 아래 이름이 대시보드 외 화면에서 "강사님" | 웹 `DashboardLayout` |
| 4 | favicon 없음 | 강사 앱 |

### B-3. 🟡 코드 구조·품질
| # | 문제 | 현재 | 해결 방향 |
|---|---|---|---|
| 1 | 큰 화면 파일 | 고객 `schedule.tsx` 1,405줄, 강사 `schedule.tsx` 1,304줄, 강사 `posts.tsx` 970줄, 강사 `passes.tsx`·`index.tsx`·고객 `match.tsx` 600줄대 | 화면 하나씩 컴포넌트로 분리 (동작·UI 그대로, 위치만 이동) |
| 2 | 두 앱에 같은 파일 | `lib/bookingUtils.ts`·`lib/alert.ts`·`lib/config.ts` 완전히 동일, `types/api.ts` 는 웹·두 앱 3벌 | `packages/api`(공통 타입·유틸)로 통합 — 요청 시에만 진행 (CLAUDE.md) |
| 3 | lint 가 검사에 없음 | 웹은 `make webcheck` 에 있지만 두 앱은 타입 검사만. 강사 앱 경고 약 21개 | 경고 정리 후 `make check`·CI 에 앱 lint 추가 |
| 4 | 쓰지 않는 의존성 | `expo-secure-store`(두 앱, 코드에서 안 씀), `zustand`(웹, 설치만 됨 — CLAUDE.md·README 스택에는 표기) | 제거하거나 스택 표기 정리 |
| 5 | 죽은 파일 | `frontend/src/store`·`types`·`utils` (0바이트 파일), `backend/alembic/README` (빈 파일) | 삭제 (참조 없음) |
| 6 | 옛 구조가 남은 곳 | 게시물 단일 미디어 컬럼(레거시, 새 글은 `post_media`), 예약 타입 `HOLIDAY`·`WORK_OVERRIDE`(DB enum·옛 마이그레이션 때문에 유지) | 데이터 확인 후 마이그레이션으로 정리 (급하지 않음) |

### B-4. 🟡 테스트 공백
| # | 문제 | 해결 방향 |
|---|---|---|
| 1 | 웹·두 앱에 자동 테스트 없음 (타입 검사·lint 만) | 핵심 화면 흐름 테스트 추가 |
| 2 | 화면 점검 도구(Playwright)가 CI 에서 안 돎 | ✅ 저장소 `tools/ui-check/` 로 옮김 (2026-10-25). 남은 것: CI 연결 |
| 3 | 압축 응답·Supabase RLS 처럼 **배포 환경에서만** 드러나는 문제 | 데모(staging 추적) 배포 후 로그인 smoke test 를 습관화 (이번에 프록시 결함을 이렇게 찾음) |

### B-5. 🟢 설정·운영 정리
| # | 문제 | 해결 방향 |
|---|---|---|
| 1 | 개발 DB 에 `z1a2b3c4d5e6` 미적용 (수동 정책이 있어 변화는 없음) | 승인 후 적용해 이력 맞추기 |
| 2 | S3 를 IAM 액세스 키로 접근 (Copilot addon 이 이미 태스크 역할 권한을 줌) | 역할만 쓰도록 정리 검토 (A 의 AWS 표 참고) |
| 3 | 실기기 터널(`make ctunnel`·`itunnel`)이 옛 위치 `apps/.env` 에서 `NGROK_AUTHTOKEN` 을 읽음 | 각 앱 폴더로 옮길지 결정 |
| 4 | staging merge 후 배포 봇이 작업 브랜치에 병합 커밋을 push | 배포 재개 때 sync job 정리 (지금은 다음 작업 전 `git pull`) |
| 5 | 피드백 공개 동의의 공개 범위 미정 | 스위치만 있음. 레슨노트 통합 후 무엇을 공개할지 결정 |
| 6 | 데모 계정 비밀번호가 공개되어 방문자가 바꿀 수 있음 | 가끔 확인, 필요하면 재설정·재시드 |

---

## C. 정해야 시작할 수 있는 것 (사용자 결정)

| 정할 것 | 고를 내용 | 영향 |
|---|---|---|
| **회원가입 방식** | 이메일만 / 소셜 로그인(카카오·구글 등) 추가. 강사도 앱에서 가입하는지 | A-1 #1 |
| **강사 승인 운영 방식** | 강사가 신청 → 관리자 승인 / 합의 후 관리자가 계정 생성 | A-1 #3 |
| **관리자 웹 범위** | 첫 출시는 강사 승인·회원 관리만 / 시스템·통계까지 | A-1 #3 |
| **결제 범위** | 앱 결제(PG 연동, 사업자등록·통신판매업 신고) / 현장 결제 + 수동 기록으로 시작 | A-1 #5 |
| **앱 출시 형태** | 스토어 설치형 / 우선 웹(브라우저) 버전으로 시작 | A-2 |
| **약관·개인정보처리방침 내용** | 수집 항목, 보관 기간, 마케팅 동의 여부 (문서 내용은 직접 확정) | A-1 #2 |
| **피드백 공개 범위** | 공개 동의 스위치만 있음. 무엇을 누구에게 공개할지 | B-5 #5 |
| **웹 "💬 피드백" 버튼** | 강사 앱처럼 제거할지 (UI 변경) | B-1 #1 |
| **모임 찾기 사양** | 모집 인원, 마감, 신청·취소, 모임 채팅 | 출시 후 |
| 작은 결정 | 데모를 출시 후에도 유지할지 · `packages/api` 통합 여부 · 실기기 터널 env 위치 · `zustand` 스택 표기 | B-3, B-5 |

**먼저 정하면 좋은 것**: 회원가입 방식, 강사 승인 방식 (출시 필수 #1·#3 이 여기에 달려 있음)

## D. 결정 없이 바로 할 수 있는 것 (요청하면 진행)

| 할 일 | 비고 |
|---|---|
| 죽은 파일 삭제 (0바이트 파일 4개), 쓰지 않는 `expo-secure-store` 제거 | B-3 #4·#5 |
| 큰 화면 파일 분리 | 동작·UI 그대로, 위치만 이동 (B-3 #1) |
| 화면 다듬기 (영어 원문, `bookings` 제목, "강사님", favicon) | 바꿀 문구만 확인 후 진행 (B-2) |
| 앱 lint 경고 정리 + 검사·CI 에 추가 | B-3 #3 |
| 화면 점검 도구 CI 연결 (저장소로 옮기기는 완료) | B-4 #2 |
| 로그인 전 401 로그 정리 | B-1 #3 |
| 개발 DB 에 `z1a2b3c4d5e6` 적용 | 원격 DB 라 실행 직전 승인 (B-5 #1) |
