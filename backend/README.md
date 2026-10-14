# Backend — FastAPI

CRM Core의 백엔드 서버입니다.
FastAPI(async) + SQLModel + PostgreSQL(AsyncPG) + Alembic 기반.

---

## Quick Start

```bash
# 저장소 루트에서 (Docker 필요, 외부 서비스·backend/.env 불필요)
make apitest     # 로컬 DB로 테스트
make apiverify   # 로컬 DB → 서버 → 토큰 → 플로우까지 원클릭
```

- 로컬 Postgres 컨테이너(`crm-local-db`)를 자동으로 띄우고 더미 설정(`scripts/local_env.sh`)으로 실행

---

## Common Commands

| 명령 | 설명 |
|------|------|
| `make api` | 개발 서버 실행 |
| `make apitest` | 테스트 실행 (로컬 DB 새로 만들기 + alembic check + pytest) |
| `make apiverify` | 원클릭 로컬 검증 (로컬 DB + 서버 + 토큰 + 플로우) |
| `make apitoken` | 실제 Supabase 토큰 발급 |
| `make apiflow` | 실행 중인 서버에 플로우 실행 |
| `make gitrelease` | main 버전 태그 생성 (롤백 기준점 · 대화형) |
| `make gitrollback` / `make gitrollbackdry` | 롤백 실행 / 롤백 시뮬레이션 |
| `make gitbranch` | 브랜치 리셋 |
| `make dbcheck` / `make dbschema` | DB 연결 / 스키마 검증 |
| `make stglogs` / `make prodlogs` | 스테이징 / 운영 로그 |

전체 명령어 목록은 `../docs/operations/dev-runbook.md` 참고.

---

## 로컬 개발 환경 설정

**요구사항**: Python 3.11, Poetry, Docker (테스트용 로컬 Postgres 컨테이너)

```bash
# 의존성 설치
cd backend
poetry install

# 환경변수 설정 (.env.example 참고, 변수 설명은 docs/operations/env-setup.md)
cp .env.example .env
# DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET, SECRET_KEY 필수 설정

# 서버 실행 (저장소 루트에서)
make api
```

> `backend/.env` 의 DB 는 원격 Supabase 입니다. 원격에 `alembic upgrade` 는 **승인 후에만** 실행합니다. 모델과 원격 DB 차이는 `make migcheck`(읽기 전용)로 확인합니다.

---

## 도메인 구조

| 도메인 | 기능 |
|--------|------|
| `auth` | Supabase 기반 인증 · JIT 유저 생성 · 아이디/비밀번호 로그인 |
| `users` | 사용자 관리 · RBAC (CUSTOMER / INSTRUCTOR / CONTENT_MANAGER / ADMIN) · 담당 강사 지정 · 회원 탈퇴(기록 보존) |
| `instructor` | 강사 승인 · 담당 고객 등록 · 공개 프로필 · 매출·운영 대시보드 |
| `calendar` | 캘린더 · 타임슬롯 · 휴무(정기·임시·날짜별 열기/닫기) · 예약 가능 시간 |
| `booking` | 레슨 예약 신청 · 확정·거절·취소·완료·노쇼 · 수강권 차감 |
| `lesson_notes` | 레슨노트 (글 · 스캔 PDF, 고객별) |
| `passes` | 수강권 상품 · 발급 · 사용 관리 |
| `payment` | 결제 기록 · 상태 관리 (5년 보존) |
| `promotions` | 강사 할인·이벤트 프로모션 (프로토타입) |
| `posts` | 게시물(홍보·공지·커뮤니티) · 댓글 · 좋아요 · 미디어 |
| `notifications` | 알림 (댓글·좋아요 등) |
| `chat` | 고객–강사 1:1 채팅 (문의하기) |
| `matching` | 강사 매칭 신청 API · 모임 찾기(예정) |

```
backend/app/domains/{feature}/
  ├── models.py
  ├── schemas.py
  ├── router.py
  └── repository.py
```

각 도메인은 위 4파일 구조를 따르며, router에 비즈니스 로직을 작성하지 않습니다.

---

## 마이그레이션 (Alembic)

```bash
# 새 마이그레이션 생성
poetry run alembic revision --autogenerate -m "설명"

# 최신으로 업그레이드
poetry run alembic upgrade head

# 히스토리 확인
poetry run alembic history --verbose
```

> **규칙**: 이미 공유/배포된 revision은 절대 수정하지 않는다.
> 자세한 내용은 루트 `CLAUDE.md` 섹션 9 참고.

---

## 테스트

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_auth.py` · `test_password_login.py` | 토큰 검증·폴백, 최초 로그인 생성, 역할 확인, 비밀번호 로그인 |
| `test_users.py` · `test_users_api.py` | 내 정보, 역할별 목록, 계정 관리, 결제·계약 기록 보존, 탈퇴 |
| `test_instructor.py` | 스태프, 강사 신청·승인, 공개 목록, 담당 고객 등록 |
| `test_calendar.py` · `test_booking_flow.py` · `test_bookings.py` | 슬롯, 휴무, 예약 상태 전환, 중복 방지, 수강권 차감 |
| `test_passes.py` · `test_payment.py` | 수강권 발급·사용, 결제 등록 권한·수강권 연결 |
| `test_lesson_notes.py` · `test_posts.py` · `test_consent_policy.py` | 레슨노트, 게시물·댓글·좋아요, 피드백 공개 동의 |
| `test_chat.py` · `test_inquiry.py` · `test_match_request.py` | 채팅, 문의하기 → 담당 강사 지정, 매칭 요청 |
| `test_promotions_dashboard.py` | 프로모션, 매출 대시보드, 한국 날짜 기준 |

```bash
# 저장소 루트에서 (로컬 DB 컨테이너, 원격 DB 연결 없음)
make apitest
make apitest ARGS="-k booking"   # 일부만
```

테스트는 outer transaction + savepoint 방식으로 격리됩니다.
각 테스트 후 DB 데이터가 자동 롤백되어 환경이 깨끗하게 유지됩니다.

---

## 참고 문서

| 문서 | 내용 |
|------|------|
| `../docs/operations/dev-runbook.md` | 개발 명령어 모음 |
| `../docs/operations/troubleshooting.md` | 문제 해결 |
| `../docs/operations/aws.md` | AWS / Copilot 운영 가이드 |
| `../docs/operations/env-setup.md` | env 파일·변수 이름 |
| `../docs/operations/pg-integration.md` | PG(온라인 결제) 연동 방법 |
| 루트 `README.md` | 배포 파이프라인 |