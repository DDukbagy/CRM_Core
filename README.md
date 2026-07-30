# CRM Core

골프 레슨 중심 CRM 시스템 — 강사·고객·관리자를 하나의 플랫폼으로 연결합니다.

## 구조

```
CRM_Core/
├── backend/          # FastAPI 백엔드 (Python)
├── frontend/         # 관리자·강사용 웹 포털 (Next.js)
├── apps/customer/    # 고객 모바일 앱 (Expo React Native)
├── apps/instructor/  # 강사 모바일 앱 (Expo React Native)
└── packages/         # 공통 패키지 (api, ui — 예정)
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | FastAPI · SQLModel · PostgreSQL (AsyncPG) · Alembic · Poetry · slowapi · Sentry |
| 관리자·강사 웹 | Next.js 16 · React 19 · Supabase Auth · Zustand · TanStack Query · Tailwind CSS |
| 고객 앱 | Expo · React Native · Expo Router · Supabase Auth · Sentry |
| 강사 앱 | Expo · React Native · Expo Router · Supabase Auth · Sentry |
| 인증 | Supabase JWT (주) · HS256 로컬 JWT (폴백) · RBAC |
| 파일 저장소 | AWS S3 — 게시물·레슨 관련 미디어 |
| 배포 | AWS Copilot (환경별 Manifest + Addon) · GitHub Actions |

## 주요 기능

| 도메인 | 기능 |
|--------|------|
| `auth` | Supabase 기반 인증 · JIT 유저 생성 |
| `users` | 사용자 관리 · RBAC (CUSTOMER / INSTRUCTOR / CONTENT_MANAGER / ADMIN) |
| `instructor` | 강사 승인 · 담당 고객 등록 · 강사 공개 프로필 검색 |
| `calendar` | 캘린더 · 타임슬롯 · 예약 · 레슨노트 · 활성 예약 중복 방지 |
| `membership` | 멤버십 관리 (횟수제 / 기간제) |
| `payment` | 결제 내역 기록 · 상태 관리 |
| `passes` | 레슨 패스(수강권) 발급 · 사용 관리 |
| `posts` | 게시물 · 댓글 · 좋아요 · 미디어 · 동의 정책 · 매칭 요청(수락 시 예약 자동 생성) |
| `chat` | 채팅 |
| `content` | 강사 콘텐츠 관리 |

각 도메인은 `models.py / schemas.py / router.py / repository.py` 구조를 따릅니다.

## 인증 흐름

1. Supabase Auth 로그인 및 세션 발급
2. 백엔드에서 Supabase JWT 검증 (개발용 폴백: HS256 로컬 JWT)
3. 최초 로그인 시 JIT 유저 자동 생성
4. RBAC 역할 검증 — 권한 없는 사용자는 `/forbidden` 처리
5. 웹은 Next.js `/api/[...path]` 프록시를 통해서만 백엔드 호출

## 빠른 시작

각 컴포넌트별 상세 가이드는 해당 폴더의 README를 참고하세요.

```bash
# 백엔드
cd backend && make server

# 관리자·강사 웹
cd frontend && npm run dev

# 고객 앱
cd apps/customer && npx expo start

# 강사 앱
cd apps/instructor && npx expo start
```

> **참고**: Expo 앱은 각 앱 루트에 자체 `.env` 파일이 필요합니다 (`apps/customer/.env`, `apps/instructor/.env`). 상위 디렉터리의 `.env`는 읽지 않습니다.

---

## 배포 파이프라인

**"Code Push → CI → Staging Deploy → Main Merge → Prod Deploy"**

### 1단계: 개발 (Development)

1. 작업 브랜치 생성 (`feature/*` 또는 `fix/*`)
2. 코드 작성 후 `git commit` → `git push`
3. GitHub에서 PR 생성 (`feature` → `staging`)
4. **CI** 자동 실행 (백엔드 테스트 + 프론트 린트/빌드)

### 2단계: 스테이징 배포 (Staging)

5. CI 통과 후 `staging` 브랜치로 Merge
6. **deploy-staging** 워크플로우 자동 실행 (CI 포함)
7. 배포 성공 시 **"Release: Staging → Main"** PR 자동 생성

### 3단계: 운영 배포 (Production)

8. 자동 생성된 PR 확인 후 Merge 버튼 클릭
9. **deploy-prod** 워크플로우 자동 실행 (CI 포함)
10. 운영 배포 완료

> **현재 운영 상태**: AWS 환경은 비용 절감을 위해 중단된 상태입니다. 스테이징 실환경 검증 게이트는 AWS 재가동 시 활성화됩니다.

### 수동 배포 (긴급 복구)

```bash
make copilot-deploy-staging
make copilot-deploy-prod
```

### 로그 확인

```bash
make copilot-logs-staging
make copilot-logs-prod
```

---

## 운영 원칙

- CI 실패 상태에서 Merge 금지
- Staging 확인 없이 Prod 배포 금지
- Prod 배포는 항상 PR 승인 단계를 거친다
- 이미 공유/배포된 Alembic revision은 절대 수정하지 않는다

## 환경

| 구분 | Copilot 환경명 | 용도 |
|------|---------------|------|
| 로컬 | `local` | 로컬 / Codespace 개발 |
| 스테이징 | `staging` | 운영 배포 전 AWS 리허설 환경 |
| 운영 | `prod` | 실제 운영 환경 |

> 운영 명령·환경변수에서는 항상 Copilot 환경명(`prod`)을 사용합니다.

## 테스트

CI에서 백엔드 테스트와 프론트 린트/빌드가 실행됩니다.

| 테스트 | 검증 내용 |
|--------|-----------|
| `tests/test_bookings.py` | 예약 생성 · 중복 예약 정책 (취소된 예약은 중복 판정에서 제외) |
| `tests/test_consent_policy.py` | 게시물 · 미디어 동의 정책 |

```bash
cd backend
poetry run pytest
```

## 장애 대응 체크리스트

1. CI 상태 확인
2. Staging 상태 확인
3. 로그 확인 (`make copilot-logs-staging` / `make copilot-logs-prod`)
4. 환경변수·시크릿 확인
5. DB 진단

```bash
cd backend
poetry run python scripts/check_db_connection.py   # DB 연결 확인
poetry run python scripts/check_schema.py          # 스키마 확인
bash scripts/verify.sh                             # 전체 검증
```

## 문서

| 문서 | 내용 |
|------|------|
| `backend/README.md` | 백엔드 개발 가이드 |
| `frontend/README.md` | 관리자·강사 웹 개발 가이드 |
| `apps/customer/README.md` | 고객 앱 개발 가이드 |
| `apps/instructor/README.md` | 강사 앱 개발 가이드 |
| `backend/Docs/` | AWS 운영 · 개발 Runbook · 트러블슈팅 |