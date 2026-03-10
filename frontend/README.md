# Frontend — 관리자 웹 (Next.js)

CRM Core의 관리자용 웹 대시보드입니다.
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

백엔드 URL은 `/api/[...path]` 프록시 경유 — 클라이언트에서 직접 호출하지 않습니다.

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

## API 호출 구조

모든 백엔드 요청은 `/api/[...path]` 프록시를 통해 전달됩니다.
클라이언트에서 백엔드 URL을 직접 사용하지 않습니다.

```
클라이언트 → /api/[...path] (Next.js 프록시) → FastAPI 백엔드
```

---

## 주요 스크립트

```bash
npm run dev      # 개발 서버 (HMR)
npm run build    # 프로덕션 빌드
npm run lint     # ESLint 검사
npm run start    # 프로덕션 서버
```

---

## 폴더 구조

```
src/
├── app/         # App Router 페이지 및 API 프록시 (/api/[...path])
├── components/  # 공통 컴포넌트
├── stores/      # Zustand 스토어
└── lib/         # 공통 유틸
```
