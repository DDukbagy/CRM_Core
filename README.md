# CRM Core

골프 레슨 중심 CRM 시스템 — 강사·고객·관리자를 하나의 플랫폼으로 연결합니다.

## 구조

```
CRM_Core/
├── backend/          # FastAPI 백엔드 (Python)
├── frontend/         # 관리자 웹 (Next.js)
├── apps/customer/    # 고객 모바일 앱 (Expo React Native)
└── packages/         # 공통 패키지 (api, ui — 예정)
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | FastAPI · SQLModel · PostgreSQL (AsyncPG) · Alembic · Poetry |
| 관리자 웹 | Next.js 16 · React 19 · Zustand · TanStack Query · Tailwind CSS |
| 고객 앱 | Expo · React Native · Expo Router · Supabase Auth |
| 인증 | Supabase JWT (주) · HS256 로컬 JWT (폴백) · RBAC |
| 배포 | AWS Copilot · GitHub Actions |

## 빠른 시작

각 컴포넌트별 상세 가이드는 해당 폴더의 README를 참고하세요.

```bash
# 백엔드
cd backend && make server

# 관리자 웹
cd frontend && npm run dev

# 고객 앱
cd apps/customer && npx expo start
```

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

## 환경

| 환경 | 용도 |
|------|------|
| local | 로컬 / Codespace 개발 |
| staging | AWS 리허설 환경 |
| production | 실제 운영 환경 |

## 장애 대응 체크리스트

1. CI 상태 확인
2. Staging 상태 확인
3. 로그 확인 (`make copilot-logs-staging` / `make copilot-logs-prod`)
4. 환경변수·시크릿 확인

## 문서

- `backend/README.md` — 백엔드 개발 가이드
- `frontend/README.md` — 관리자 웹 개발 가이드
- `apps/customer/README.md` — 고객 앱 개발 가이드
- `backend/docs/` — 상세 운영·디버깅 문서
