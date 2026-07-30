# Frontend — 관리자·강사용 웹 포털 (Next.js)

CRM Core의 관리자·강사용 웹 포털입니다.
Next.js 16 (App Router) + React 19 + TanStack Query + Zustand + Tailwind CSS 기반.

---

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000` 에서 확인합니다.

---

## 환경변수

`.env.local` 파일을 생성하고 아래 변수를 설정합니다.

```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

> 백엔드 URL은 `/api/[...path]` 프록시 경유 — 클라이언트에서 직접 호출하지 않습니다.

---

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 프레임워크 | Next.js 16 (App Router) |
| UI | React 19 · Tailwind CSS |
| 서버 상태 | TanStack Query |
| 클라이언트 상태 | Zustand |
| 인증 | Supabase Auth |

---

## 주요 화면

| 경로 | 역할 | 내용 |
|------|------|------|
| `/login` | 공개 | 로그인 |
| `/admin` | ADMIN | 관리자 대시보드 (강사 관리 · 시스템 관리 · 영업/통계) |
| `/instructor` | INSTRUCTOR | 강사 대시보드 |
| `/schedule` | 인증 필요 | 스케줄 관리 |
| `/forbidden` | — | 권한 없는 사용자 안내 |

---

## 인증·API 호출 구조

```
클라이언트 → Supabase Auth 로그인
          → /api/auth/sync (백엔드 사용자·역할 동기화)
          → (protected) 레이아웃에서 역할 검사
          → /api/[...path] (Next.js 프록시) → FastAPI 백엔드
```

1. Supabase Auth 로그인 및 세션 발급
2. `/api/auth/sync`로 백엔드 사용자·역할 동기화
3. `(protected)` 레이아웃에서 역할 검사 — 권한이 없으면 `/forbidden`
4. 모든 백엔드 요청은 `/api/[...path]` 프록시가 토큰을 첨부해 전달

> **금지**: 클라이언트에서 백엔드 직접 호출 · JWT를 localStorage에 저장 · 백엔드 URL 하드코딩

---

## 주요 스크립트

| 명령 | 설명 |
|------|------|
| `npm run dev` | 개발 서버 (HMR) |
| `npm run build` | 프로덕션 빌드 |
| `npm run lint` | ESLint 검사 |
| `npm run start` | 프로덕션 서버 |

---

## 폴더 구조

```
src/
├── app/
│   ├── (protected)/     # 인증 필요 영역 (admin / instructor / schedule)
│   ├── login/           # 로그인
│   ├── forbidden/       # 권한 없음 안내
│   └── api/
│       ├── auth/sync/   # 백엔드 사용자·역할 동기화
│       └── [...path]/   # 백엔드 프록시
├── components/          # 공통 컴포넌트
├── stores/              # Zustand 스토어
└── lib/
    └── supabase/        # Supabase 클라이언트 (client / server)
```