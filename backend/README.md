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

```bash
make server              # 개발 서버 실행
make test                # 테스트 실행
make verify              # 원클릭 검증 (서버 + 토큰 + 플로우)
make tokens              # 테스트 토큰 발급
make flow                # 플로우 실행
make release             # 스테이징 배포
make rollback            # 롤백
make rollback-dry        # 롤백 시뮬레이션
make branch-reset        # 브랜치 리셋
make copilot-logs-staging  # 스테이징 로그
make copilot-logs-prod     # 운영 로그
```

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

```
app/domains/
├── users/          # 사용자 관리 (RBAC 역할 포함)
├── calendar/       # 캘린더·타임슬롯·예약·레슨노트
├── instructor/     # 강사 관리·매칭 요청·출석 통계
├── membership/     # 멤버십 (횟수제/기간제)
└── payment/        # 결제 내역
```

각 도메인은 `models.py / schemas.py / router.py / repository.py` 구조를 따릅니다.

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

**규칙**: 이미 공유/배포된 revision은 절대 수정하지 않는다.
자세한 내용은 루트 `CLAUDE.md` 섹션 10 참고.

---

## 테스트

```bash
# 전체 테스트
poetry run pytest

# 특정 파일
poetry run pytest tests/test_bookings.py -v

# 빠른 확인
poetry run pytest tests/test_bookings.py -q
```

테스트는 outer transaction + savepoint 방식으로 격리됩니다.
각 테스트 후 DB 데이터가 자동 롤백되어 환경이 깨끗하게 유지됩니다.

---

## 참고 문서

- `docs/dev-runbook.md` — 개발 명령어 모음
- `docs/troubleshooting.md` — 문제 해결
- `docs/aws.md` — AWS / Copilot 운영 가이드
- 배포 파이프라인 → 루트 `README.md` 참고
