# 진행 현황 (CRM_Core)

> 세션 시작 시 이 파일을 먼저 읽는다. 세션 종료 시 §3~§6 을 갱신한다.
> 규칙(무엇을 지켜야 하는가)은 CLAUDE.md, 상태(어디까지 했는가)는 이 파일에 둔다. 자세한 변경 이력은 git log.
> 마지막 갱신: 2026-10-14 (데모 배포: Render·Vercel·Supabase 데모)

## 관련 문서

| 문서 | 내용 |
|---|---|
| [operations/dev-runbook.md](operations/dev-runbook.md) | make 명령 모음 (실행·검사·DB·마이그레이션·배포) |
| [operations/env-setup.md](operations/env-setup.md) | env 파일·변수 이름·Codespace 복구 순서 |
| [operations/verification.md](operations/verification.md) | 실제 Supabase 로그인·앱·웹·S3 검증 절차 (사용자 실행) |
| [operations/pg-integration.md](operations/pg-integration.md) | PG(온라인 결제) 연동 방법 |
| [operations/troubleshooting.md](operations/troubleshooting.md) | 자주 겪은 문제와 해결 |
| [operations/aws.md](operations/aws.md) | AWS·Copilot 배포 (배포 재개 시) |
| [portfolio/performance-db-connection.md](portfolio/performance-db-connection.md) | 포트폴리오: 앱 로딩 속도 개선(DB 커넥션 풀) 원인·측정·해결 |
| [requirements/CRM_Requirements_v1.0.html](requirements/CRM_Requirements_v1.0.html) | 요구사항 원본 |

---

## 1. 목표와 작업 방식

- 포트폴리오의 **주력** 프로젝트. 최우선 가치는 **일관성과 가독성**(폴더·파일명·구조만 보고 역할을 이해).
- (D4) **모든 기능이 에러 없이 동작**하게 만든 뒤, 포트폴리오에 주요 기능·폴더 구조와 그 이유를 쓴다. 모임 찾기는 맨 마지막.
- 기존 기능·버튼·"준비 중" 화면은 지우지 않는다. 완전히 죽은 코드(진입 경로·참조 없음)만 지운다. 기능·UI 는 임의로 바꾸지 않고 먼저 묻는다.
  - 화면이 없는 백엔드 기능은 git 이력부터 본다. 예전에 화면이 있었으면 "빠진 기존 기능"으로 복원 대상
- 선택지가 있는 결정은 **선택지·장단점·권장안**을 제시하고 사용자가 고른다. 결정과 이유는 §7 에 한두 줄로.
- 커밋·push·PR 은 사용자가 요청할 때만.

---

## 2. 현재 상태 (2026-10-14)

| 영역 | 상태 |
|---|---|
| 백엔드 | 13개 도메인(auth, booking, calendar, chat, instructor, lesson_notes, matching, notifications, passes, payment, posts, promotions, users) 모두 `models/schemas/repository/router`. router 는 요청·권한·응답만, 규칙은 repository |
| 테스트 | pytest **183개** 통과, `make check`(백엔드·웹·두 앱) 통과. 로컬 Postgres 컨테이너, 원격 DB 미사용 |
| 원격 DB (Supabase) | **개발 DB**: head `y0z1a2b3c4d5` (`z1a2b3c4d5e6` 미적용 — 수동 정책이 이미 있어 적용해도 변화 없음, 원격 적용은 승인 후). 2026-10-14 일시 중지 상태 → Restore 필요<br>**데모 DB**(별도 프로젝트): head `z1a2b3c4d5e6`, 데모 데이터 시드 완료 |
| 강사 웹 (`/instructor`) | 대시보드·고객 관리·스케줄·게시물·**레슨노트**·매출·**매출 분석**·**프로모션**·내 정보 |
| 관리자 웹 (`/admin`) | 대시보드 자리만. 강사 관리·시스템 관리·영업/통계 = "준비 중" |
| 강사 앱 | 대시보드·고객 관리·스케줄(휴무 5종)·채팅·글쓰기·**레슨노트**·매출(+운영 현황, 확인 전용)·내 정보·수강권 관리 |
| 고객 앱 | 홈·달력(예약)·게시글(좋아요·댓글)·**레슨노트**·채팅·강사 찾기(프로필 → 문의하기)·수강권(프로모션 안내)·내 정보(탈퇴)·스토어(준비 중) |
| 배포 | **정식(AWS Copilot)**: 오프라인. CI 검증 job 정상, deploy job 실패는 정상<br>**데모(포트폴리오용 임시)**: Render 백엔드 · Vercel 3개(`crm-core-demo-web`·`-customer`·`-instructor`) · 데모 Supabase, 모두 `staging` 추적. 링크·계정은 README |
| 브랜치 | `crm` → `staging` squash merge 로 진행. PR #73(10-04 대규모 정리), #74(커넥션 풀·한국 날짜·주석), #75(README·users 정책 마이그레이션·데모 설정), #76(프록시 압축 응답 수정·데모 수정), #77(문서) — 모두 CI 통과. **main 미반영** — 정식 배포 재개 때 Release PR(`make gitpr`, 실제 인프라 smoke test 1회 후). merge 후 GitHub 봇이 `crm` 에 병합 커밋을 push 하므로 다음 작업 전 `git pull`. `gh` 미설치라 PR·CI 는 Codespace GitHub 토큰으로 API 호출 |

---

## 3. 지금까지 한 일 (요약)

### 구조
- 도메인 재편: lesson_notes·matching·notifications·booking 분리, posts+content 병합, 로그인 API → auth, 멤버십 → 수강권 통합(도메인 삭제), promotions 신설
- 전 도메인 repository 전환. 도메인 사이 호출은 repository 끼리 같은 세션(한 트랜잭션)
- 백엔드 폴더: `app/domains/{기능}` 4파일(models·schemas·router·repository) + 공통은 `app/core`(auth·config·exceptions·middleware·health·push·s3·retention·clock·constants)와 `app/db`(base·models 등록·session). 흩어져 있던 단독 파일을 이 둘로 모음
- import 정리, 프론트(웹·두 앱) 구조 점검: 완전히 죽은 파일만 삭제(Expo 템플릿 잔재 등), 준비 중 페이지·기존 버튼은 유지
- 웹: 개발용 `dev-login` 제거, 관리자 메뉴(`admin/nav.ts`) 공용화 + 404 나던 메뉴를 "준비 중" 페이지(`ComingSoon`)로
- 마이그레이션 (모두 원격 리허설 → 승인 → 적용): `p0` 전 테이블 RLS · `q1` 옛 게시물 데이터 정리 · `r2` FK 정렬 · `s3` 결제 회원 삭제 제한 · `t4` 탈퇴 상태 · `u6` 휴무 재설계(calendar_blocks) · `v7` 계약 기록 보존·withdrawn_at · `w8` 멤버십 → 수강권 · `x9` 레슨노트(고객별·PDF) · `y0` 프로모션 · `z1` users 본인 행 읽기 정책(데모 DB 에만 적용)
- 문서를 `docs/operations`, `docs/requirements` 로 정리. Makefile 타깃 `<대상><동작>` 통일. 로컬 검증 명령(`make apitest`·`apiverify`·`check`)

### 결함 수정 (대표)
- 🔴 보안: 채팅 테이블 RLS 꺼짐(anon 키로 읽기·쓰기 가능) → 전 테이블 RLS, `.ics` 다운로드 권한 없음, 레슨노트 남의 예약에 작성 가능
- 데이터: 시간 휴무가 모든 날짜에 적용, 휴무가 가짜 예약으로 저장 → `calendar_blocks`(CLOSE/OPEN) 재설계, 회원 삭제로 결제·계약 기록이 지워짐 → 5년 보존 + 탈퇴 처리
- 500 오류: 결제 등록 422/500, 비밀번호 해시, 강사 고객 통계, 수강권 있는 회원 삭제, 중복 이메일 로그인
- 성능: 요청마다 DB 새 연결(`NullPool`) → 커넥션 풀. API 1,473 → 548ms, 화면 하나(API 4개) 최대 2.5초 → 약 0.6초. 다시 들어올 때마다 전체 로딩 표시하던 앱 화면 4곳 정리
- 웹 프록시: 압축 응답(Render·Cloudflare)의 `content-length` 를 그대로 넘겨 브라우저가 JSON 을 잘라 읽음 → 웹 로그인 시 역할을 못 읽어 "일반 회원" 처리. 로컬 백엔드는 압축하지 않아 안 드러남. 압축 관련 헤더를 함께 제거
- 날짜: 백엔드가 "오늘"을 서버(UTC) 날짜로 판단 → 한국 00~09시에 오늘 시작 프로모션이 고객에게 안 보임, 어제 날짜 휴무 변경 허용. `app/core/clock.today_kst()` 로 통일
- 화면: UTC 날짜 27곳(오전 0~9시 "오늘"이 어제), 채팅 9시간 어긋남, 브라우저에서 확인창·알림이 안 뜸(60곳), 웹 메뉴 이중 선택, API 주소 끝 `/` 404

### 기능
- 휴무 5종(기본 07~20시 슬롯, 정기 휴무, 임시 휴무, 정기 휴무일 열기, 특정 시간 닫기), 강사 승인 시 기본 캘린더
- 회원 탈퇴(개인정보 삭제, 기록 보존), 계약·결제 기록 5년 보존
- 강사 문의하기 → 채팅방 → 고객이 담당 강사 지정
- 레슨노트(고객별, 글·스캔 PDF, 피드백 통합) — 강사 앱·강사 웹 작성, 고객 앱 열람
- 매출 분석·프로모션(웹 수정, 앱 확인, 고객 수강권 탭 안내) — 프로토타입
- 복원: 게시글 좋아요, 피드백 공개 동의 스위치
- 강사 앱: 웹(브라우저)에서 로그아웃 안 되던 문제, 정기 휴무 요일을 "수정 → 저장" 방식으로(실수로 바로 바뀌지 않게)
- 개발 환경: `tsconfig` `baseUrl` 빨간 밑줄 제거, 편집기 Python 을 `backend/.venv` 로(노란 밑줄), `make iweb` 시 Expo 버전 확인 네트워크 오류는 재실행 또는 `EXPO_NO_DEPENDENCY_VALIDATION=1`

### 검증
- 실제 Supabase 토큰 → `/auth/me` 200, `make apiflow` 14단계(원격 DB), 두 앱 실제 로그인·로그아웃·역할 차단
- 로컬 화면 점검(Playwright): 화면 52개 열람, 버튼 동작 23개, 신기능 21개 — 전부 통과
- 재점검(로딩 개선·주석 정리 후): 화면 37개 열람(고객 11·강사 11·웹 13 + 이동 2), 다시 들어오기 3개, 신기능 10개 — 전부 통과. 이때 한국 날짜 결함 발견·수정 (회귀 테스트 추가, 백엔드 테스트 183개)
- 문서: README 7개를 코드와 대조해 다시 작성 (루트 README 에 앱별 소개·기능·스택·데모 표·아키텍처 다이어그램). 남은 날짜 주석·사실과 다른 파일 설명 수정
- 데모 배포 (10-14): `render.yaml`, 두 앱 `vercel.json`(정적 웹 빌드, 상세 화면 주소 rewrite), `scripts/seed_demo.py`(실제 API 로 데모 데이터, 단계별 이어서 실행·502 재시도), 절차서 `operations/demo-deploy.md`. 데모 3곳 실제 로그인 확인
- 주석 정리: 작업 기록식 주석·장식 구분선 제거, 파일·주요 함수 설명 추가 (코드 동작 변경 없음)

---

## 4. 테스트해야 할 것 (사용자 실행)

절차는 [verification.md](operations/verification.md).

| # | 항목 | 비고 |
|---|---|---|
| 1 | 두 앱 화면별 확인 (4-1단계) | 실제 Supabase 계정으로 홈·달력·내 정보·대시보드·스케줄 |
| 2 | 웹 실제 로그인 (5단계) | `frontend/.env.local` 필요. 웹은 로그인 후 역할을 Supabase `users` 테이블에서 직접 읽음 |
| 3 | S3 업로드 (6단계) | 게시물 사진·영상, **레슨노트 PDF** 업로드·열람·삭제. AWS 버킷·키 필요 |
| 4 | 실기기 (폰) | 푸시 알림, 사진 스캔 → PDF(브라우저에서는 안 됨), 카메라·사진 권한. `make ctunnel`·`itunnel` |
| 5 | 이번 신기능 실제 데이터로 | 문의하기 → 담당 강사 지정, 레슨노트, 프로모션, 매출 분석 |

---

## 5. 보류

| 항목 | 결정 시점·이유 |
|---|---|
| 강사 신청·관리자 승인 화면 | 강사 계정을 합의 후 만들어 주는지, 강사가 신청하는지 운영 방식 미정 (API 는 있음) |
| 결제 상태 변경(환불 등) 화면 | 사용자가 더 고민 (API 는 있음) |
| 강사 스태프 관리 | 필요하지만 구현 보류 (콘텐츠 매니저가 강사 이름으로 게시물 작성, API 는 있음) |
| PG(온라인 결제) 연동 | 배포 후. 방법은 [pg-integration.md](operations/pg-integration.md). 수강권 "결제하기"는 지금 "결제 준비 중" 안내 |
| 피드백 공개 동의의 공개 범위 | 스위치만 복원. 레슨노트로 통합한 뒤 무엇을 어디에 공개할지는 나중에 |
| 강사 웹 게시물의 "💬 피드백" 작성 | 피드백은 레슨노트로 옮겨 백엔드가 400 을 돌려줌. 강사 앱처럼 버튼을 뺄지 사용자 결정 대기 |
| 화면 경미 항목 | ① 로그인 전 홈이 잠깐 API 를 불러 401 로그 ② 강사 앱 영어 원문(`COMPLETED`, `MALE`) ③ 고객 앱 예약 목록 상단 제목 `bookings` ④ 웹 왼쪽 아래 이름이 대시보드 외에서 "강사님" ⑤ 강사 앱 favicon 없음 |
| 큰 화면 파일 분리 | 포트폴리오 직전. 고객 `schedule.tsx` 1,407줄, 강사 `schedule.tsx` 1,302줄 등. 화면 하나씩, 동작·UI 그대로 위치만 이동 |
| lint 경고 | 강사 앱 21, 고객 앱 일부. 아직 `make check`·CI 에 lint 없음 |
| 배포 관련 정리 | `deploy-staging` sync job 이 merge 된 작업 브랜치에 봇 병합 커밋을 push 함(2026-10-04 `crm` 에 `1fee94f` 생김, 내용은 staging 과 같음). 브랜치 삭제 운영과 충돌 — 배포 재개 때 정리 |

---

## 6. 해야 할 것

1. **§4 테스트** (사용자) — 결과에 따라 결함 수정
2. **데모 배포** ✅ 완료 (2026-10-14): 웹·고객 앱·강사 앱 Vercel, 백엔드 Render, 데모 전용 Supabase. 링크·계정은 README "데모" 표. 설정 체크리스트·문제 해결은 [operations/demo-deploy.md](operations/demo-deploy.md)
3. **실기기 터널 정리**: `make ctunnel`·`itunnel` 이 아직 예전 위치 `apps/.env` 에서 `NGROK_AUTHTOKEN` 을 읽음 → 각 앱 폴더로 맞출지 결정
4. **관리자 웹**: 강사 관리(승인 포함, 운영 방식 결정 후)·회원 관리(탈퇴 처리 버튼)·시스템·통계
5. **프로모션·매출 분석 고도화**(프로토타입 → 정식): 결제 연동 시 할인 실제 적용, 기간·대상 확장 여부
6. **PG 연동** (배포 후)
7. **모임 찾기** (matching 도메인, 맨 마지막): 모집 인원·마감·신청·취소·모임 채팅. 고객 앱 "모임채팅" 탭 자리만 있음
8. **정식 출시 (AWS)**: [§6-1 체크리스트](#6-1-정식-출시-체크리스트-aws) 완료 후 staging → main Release PR. 실제 인프라 smoke test 1회 후
9. **포트폴리오 정리**: 큰 화면 파일 분리 → 주요 기능·폴더 구조와 이유 작성 → 배포(실제 인프라 smoke test 1회 필수)

---

## 6-1. 정식 출시 체크리스트 (AWS)

> 2026-10-14 저장소 점검 기준. 법적 요건은 일반 기준이므로 출시 전 전문가·공식 안내로 확인.

### 🔴 출시 전 필수
| # | 할 일 | 현재 상태 |
|---|---|---|
| 1 | **회원가입·비밀번호 찾기** (고객 앱·강사 앱, 필요 시 웹) | ❌ 없음. 지금은 Supabase 대시보드에서 만든 계정으로만 로그인 |
| 2 | **이용약관·개인정보처리방침** 페이지 + 가입 시 동의(필수·선택 구분) | ❌ 없음. 앱 스토어 심사에도 개인정보처리방침 주소 필요 |
| 3 | **관리자 화면: 강사 승인·회원 관리** | API 만 있음. 운영 방식(강사 신청 vs 합의 후 생성) 결정 먼저 (§5) |
| 4 | **운영 인프라** (아래 표) | 데모만 있음 |
| 5 | **결제 범위 결정**: 앱 결제 포함 → PG 연동 필수(사업자등록·통신판매업 신고). 현장 결제 + 수동 기록으로 시작 → 결제 버튼 문구 정리 | 수강권 "결제하기" = "결제 준비 중" 안내 |
| 6 | **남은 결함·직접 테스트**: 웹 "💬 피드백" 버튼(400), 실기기(푸시·사진 스캔 → PDF·카메라), S3 업로드 | §4, §5 |

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

### 🟡 앱 스토어 출시 (설치형 앱)
- 개발자 계정: Apple(연 유료), Google Play(1회 유료)
- EAS 빌드·제출: `eas.json` 있음, 번들 ID `com.albatro.customer` · `com.albatro.instructor`
- 스토어 정보: 아이콘·스크린샷·설명·개인정보 수집 항목 표시
- 푸시: iOS APNs, Android FCM
- 계정 삭제 기능: ✅ 있음 (회원 탈퇴)

### 🟢 출시 직후 가능
화면 경미 항목, 큰 화면 파일 분리, lint 경고, `packages/api` 통합, 백업 복구 연습, 결제 상태 변경(환불) 화면, 강사 스태프 관리, 모임 찾기, 프로모션 정식화

## 6-2. 데모 유지 규칙

데모 = 포트폴리오용 임시 배포 (Render · Vercel 3개 · 데모 전용 Supabase, 모두 `staging` 추적). 정식(AWS)과 완전히 별개라 AWS 를 켜도 그대로 살아 있다.

| 바뀌는 것 | 데모 반영 | 할 일 |
|---|---|---|
| 코드 (백엔드·웹·앱) | ✅ 자동 | staging merge 후 Vercel 세 프로젝트의 맨 위 **Production** 배포 커밋이 staging 최신인지 확인 |
| **DB 구조 (마이그레이션)** | ❌ 직접 | staging merge 후 데모 DB 에 `alembic upgrade head` (demo-deploy.md 2단계 명령). 안 하면 새 코드 + 옛 DB 로 데모 오류 |
| **새 환경변수** | ❌ 직접 | Render·Vercel 대시보드에 추가 (공개 접두사 `NEXT_PUBLIC_`·`EXPO_PUBLIC_` 는 Sensitive 끄고). Vercel 은 Redeploy 필요 |
| 데모 데이터 | ❌ 그대로 | 새 기능 예시가 필요하면 `scripts/seed_demo.py` 에 단계 추가 후 재실행 (이미 있는 단계는 건너뜀) |

- 데모는 정식보다 **먼저** 새 코드를 받는다 (staging → 데모 즉시, main → AWS 는 Release PR 후). 데모가 잠깐 깨져도 실제 사용자 영향 없음
- Supabase 무료 프로젝트는 7일 미사용 시 일시 중지 → 대시보드에서 Restore. Render 무료는 15분 미사용 시 잠듦(첫 접속 30초~1분)
- 데모 값(키·주소)은 대시보드에만 둔다. `backend/.env`(개발 DB)에 넣지 않는다

**정식 출시 후 데모를 지운다면**
- 지울 것 (저장소 먼저: `render.yaml` 이 남아 있으면 merge 때마다 Render 가 배포함)
  - 저장소: `render.yaml`, `apps/*/vercel.json`, `scripts/seed_demo.py`, `operations/demo-deploy.md`, README 데모 섹션, CLAUDE.md 데모 줄
  - 대시보드: Render `crm-core-demo-api`, Vercel 데모 3개, Supabase 데모 프로젝트
- **남길 것** (데모 때 만들었지만 운영에 필요)
  - `z1a2b3c4d5e6` users 읽기 정책 마이그레이션
  - 웹 프록시 압축 헤더 수정
- 권장: AWS 운영이 안정된 뒤에 정한다 (그동안 포트폴리오 링크 유지)

## 7. 결정 기록 (요약)

| 날짜 | 결정 | 이유 |
|---|---|---|
| 09-25 | 기본 브랜치 staging, main 직접 커밋 금지 | 작업 → staging → Release PR → main |
| 09-27 | 백엔드 구조 = 도메인 우선, 도메인 안은 레이어. 공통은 `core`·`db` | package-by-feature 를 유지하고 단독 파일만 정리 |
| 09-27 | `alembic/versions__old/` 유지 | 마이그레이션 리셋 전 이력 참고용 |
| 09-30 | 독립 도메인 기준 = 자체 테이블·상태 흐름·규칙 / 여러 도메인이 사용 / 혼자 설명 가능 | 무조건 쪼개지 않음 |
| 09-30 | posts+content 병합, 게시물 종류 = 홍보·공지·커뮤니티 (피드백은 10-04 레슨노트로) | 같은 "게시물"의 중복 구현 |
| 09-30 | 미디어는 비공개 버킷 + 서명 주소 | 비공개 영상 주소가 공개되면 안 됨 |
| 09-30 | passlib 제거, bcrypt 직접 사용 | 관리 중단 라이브러리 |
| 10-01 | (D1) 개발 DB = Supabase, 테스트·검증은 로컬 컨테이너 | 테스트가 운영 데이터에 붙지 않게 |
| 10-01 | (D2) Makefile `<대상><동작>` | 짧고 이름만으로 뜻이 보이게 |
| 10-01 | (D5) `apiverify` = 로컬 DB + 로컬 더미 서명 토큰 | 외부 서비스 없이 재현 |
| 10-01 | 개발 중 AWS 배포 안 함 | 사용자 결정 |
| 10-01 | 원격 마이그레이션은 원격 스키마 복제본 리허설 → 사용자 승인 → 적용 | 공유된 revision 은 수정 불가 |
| 10-01 | 전 public 테이블 RLS (정책 없음) | anon 키는 앱에 공개된 값 |
| 10-01 | 휴무 = 매주 반복(슬롯·정기 휴무 요일) + 날짜 예외(`calendar_blocks` CLOSE/OPEN) | 날짜 조치를 전역 상태로 만들지 않는다(CLAUDE.md) |
| 10-01 | 결제 기록 5년 보존 | 전자상거래법 시행령 제6조, 국세기본법 제85조의3 |
| 10-01 | 회원 탈퇴 = 개인정보 삭제 + WITHDRAWN 상태로 기록 보존, 재로그인 403 | 보존 기간 안 기록이 있으면 삭제 불가 |
| 10-02 | 계약 기록(수강권)도 5년 보존, 예약·레슨노트·채팅은 보존 대상 아님 | 전자상거래법 "계약 기록 5년" |
| 10-02 | 준비 중 페이지·기존 기능 보존, UI 임의 수정 금지 | 사용자 규칙 |
| 10-04 | 매칭·상담 신청 → "문의하기"(채팅방) + 고객이 담당 강사 지정 | 사용자 결정. 강사의 이메일 고객 등록은 앱 밖에서 구한 고객용으로 유지 |
| 10-04 | 레슨노트 = 고객별(예약 연결 선택), 글 또는 스캔 PDF, 피드백 통합 | 피드백과 성격이 같음 |
| 10-04 | 멤버십 → 수강권 통합 | 같은 역할의 두 체계 |
| 10-04 | 강사 웹 유지. 매출 분석·프로모션은 웹 수정, 앱 확인 | 사용자 결정 |
| 10-04 | PR #73 은 squash merge, main 은 배포 재개 때 | 커밋 이력 정리(첫 커밋에 멤버십 삭제가 섞인 문제 포함). prod 는 smoke test 전 반영 금지 |
| 10-14 | 데모(포트폴리오용) 임시 배포 = Render(백엔드) · Vercel 3개(웹·앱) · 데모 전용 Supabase, `staging` 추적. **정식 출시는 AWS Copilot** | AWS 는 비용으로 오프라인. 데모 데이터가 개발·운영 DB 와 섞이지 않게 분리 |
| 10-05 | DB 커넥션 풀(5+5), `pool_recycle=300`, `pool_pre_ping=False` | 10분 쉰 연결도 안 끊김(실측). pre_ping 이 요청마다 약 250ms. 끊기면 요청 1번만 실패 후 복구(실측). 잦아지면 True 로 |

---

## 8. 주의할 것 (재발 방지)

- **init 마이그레이션 함정**: `91d68413f8d6` 가 `create_all` 로 *현재* 모델을 만든다. 모델을 바꾸면 빈 DB 구축이 달라짐
  - passes·chat·promotions 는 `app/db/models.py` 에 등록하지 않고 `alembic/env.py` 가 비교 명령 때만 올림
  - 지운 컬럼을 옛 마이그레이션이 참조하면 `env.py` 가 upgrade 때만 잠시 붙임(예: `payments.membership_id`)
  - 모델 변경 시 `make apitest`(빈 DB) + `make migcheck`(원격) 둘 다 통과해야 함
- **Expo env 우선순위**: `.env.local` > `.env` > 셸 변수. 화면 점검용 임시 `.env.local` 이 남아 있으면 앱이 엉뚱한 주소로 요청함
- **Codespace 재시작 시 `/tmp` 삭제**: 화면 점검 도구는 저장소 밖 `/workspaces/.crm-ui-check` 에 둠(커밋 안 됨)
- **Codespace 는 언제든 삭제될 수 있다**: 남아야 할 것은 커밋·푸시, 비밀값은 Codespaces Secrets
- **"오늘" 판단은 `today_kst()`**: `date.today()` 는 서버(UTC) 날짜라 한국 00~09시에 하루 전이 된다. 앱·웹은 `toLocalDateStr`
- **`users` 본인 행 읽기 정책**: 개발 DB 에는 대시보드에서 수동으로 만들어져 있었고 마이그레이션에 없었다 → `z1a2b3c4d5e6` 추가 (Supabase 일 때만, SELECT 정책이 이미 있으면 건너뜀). 원격 개발 DB 에는 아직 미적용 (적용해도 수동 정책이 있어 변화 없음)
- **Supabase 무료 프로젝트는 7일 미사용 시 일시 중지**: 2026-10-14 개발 DB 연결 실패(tenant not found) → 대시보드에서 Restore
- **프록시는 압축을 푼 본문을 넘긴다**: `content-encoding`·`content-length` 를 같이 지워야 한다. 로컬(압축 없음)에서는 재현되지 않으므로 배포 환경에서 웹 로그인으로 확인
- **Vercel 프로젝트마다 Production 브랜치가 따로다**: 웹이 `main` 추적 상태라 merge 가 데모에 안 올라감(2026-10-14). 세 프로젝트 모두 Branch Tracking = `staging`
- **DB 연결 방식**: `NullPool` 로 되돌리지 않는다(요청마다 연결 약 0.9초). 끊김 오류가 나면 `pool_pre_ping=True` 로 대응
- env 파일은 열람·검색·출력 금지(CLAUDE.md §4). 원격 확인은 결과만 보고
