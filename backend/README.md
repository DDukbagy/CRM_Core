# Backend — FastAPI

CRM Core의 백엔드 서버입니다.
FastAPI(async) + SQLModel + PostgreSQL(AsyncPG) + Alembic 기반.

---

## Quick Start

```bash
# 최초 1회
chmod +x scripts/verify.sh
make verify
```

- 서버가 꺼져 있으면 자동 실행
- 토큰 발급 → 플로우 실행까지 원클릭

---

## Common Commands

| 명령 | 설명 |
|------|------|
| `make server` | 개발 서버 실행 |
| `make test` | 테스트 실행 |
| `make verify` | 원클릭 검증 (서버 + 토큰 + 플로우) |
| `make tokens` | 테스트 토큰 발급 |
| `make flow` | 플로우 실행 |
| `make release` | 운영 배포 (main 태그 기반 · 대화형) |
| `make rollback-safe` / `make rollback-dry` | 롤백 실행 / 롤백 시뮬레이션 |
| `make branch-reset` | 브랜치 리셋 |
| `make check-db` / `make check-schema` | DB 연결 / 스키마 검증 |
| `make copilot-logs-staging` / `make copilot-logs-prod` | 스테이징 / 운영 로그 |

전체 명령어 목록은 `Docs/dev-runbook.md` 참고.

---

## 로컬 개발 환경 설정

**요구사항**: Python 3.11, Poetry, PostgreSQL 16

```bash
# 의존성 설치
cd backend
poetry install

# 환경변수 설정 (.env.example 참고)
cp .env.example .env
# DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET, SECRET_KEY 필수 설정

# DB 마이그레이션
poetry run alembic upgrade head

# 서버 실행
poetry run uvicorn app.main:app --reload
```

---

## 도메인 구조

| 도메인 | 기능 |
|--------|------|
| `auth` | 인증 · JIT 유저 생성 |
| `users` | 사용자 관리 · RBAC (CUSTOMER / INSTRUCTOR / CONTENT_MANAGER / ADMIN) |
| `instructor` | 강사 승인 · 담당 고객 등록 · 공개 프로필 검색 |
| `calendar` | 캘린더 · 타임슬롯 · 예약 · 레슨노트 |
| `membership` | 멤버십 (횟수제 / 기간제) |
| `payment` | 결제 내역 기록 · 상태 관리 |
| `passes` | 레슨 패스(수강권) 발급 · 사용 관리 |
| `posts` | 게시물 · 댓글 · 좋아요 · 미디어 · 동의 정책 · 매칭 요청 |
| `chat` | 채팅 |
| `content` | 강사 콘텐츠 관리 |

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
> 자세한 내용은 루트 `CLAUDE.md` 섹션 10 참고.

---

## 테스트

| 테스트 | 검증 내용 |
|--------|-----------|
| `tests/test_bookings.py` | 예약 생성 · 중복 예약 정책 (취소된 예약은 중복 판정에서 제외) |
| `tests/test_consent_policy.py` | 게시물 · 미디어 동의 정책 |

```bash
# 전체 테스트
poetry run pytest

# 특정 파일
poetry run pytest tests/test_bookings.py -v
```

테스트는 outer transaction + savepoint 방식으로 격리됩니다.
각 테스트 후 DB 데이터가 자동 롤백되어 환경이 깨끗하게 유지됩니다.

---

## 참고 문서

| 문서 | 내용 |
|------|------|
| `Docs/dev-runbook.md` | 개발 명령어 모음 |
| `Docs/troubleshooting.md` | 문제 해결 |
| `Docs/aws.md` | AWS / Copilot 운영 가이드 |
| 루트 `README.md` | 배포 파이프라인 |