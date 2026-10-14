# Frontend — 관리자·강사용 웹 포털 (Next.js)

CRM Core의 관리자·강사용 웹 포털입니다.
Next.js 16 (App Router) + React 19 + TanStack Query + Zustand + Tailwind CSS 기반.

---

## Quick Start

```bash
cd frontend && npm install
cd .. && make web    # 백엔드(make api)도 켜져 있어야 데이터가 나옵니다
```

`http://localhost:3000` 에서 확인합니다. 로그인한 계정의 역할에 따라 강사는 `/instructor`, 관리자는 `/admin` 으로 이동합니다.

---

## 환경변수

`.env.local` 파일을 생성하고 아래 변수를 설정합니다.

```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
API_BASE_URL=http://localhost:8000
```

> `API_BASE_URL` 은 웹 서버(프록시)만 사용합니다. 브라우저는 `/api/[...path]` 프록시만 호출하고 백엔드를 직접 부르지 않습니다. 자세한 내용은 `docs/operations/env-setup.md`.

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
| `/instructor` | INSTRUCTOR | 대시보드 (레슨 신청 확정·거절, 취소 신청, 오늘 예약) |
| `/instructor/customers` | INSTRUCTOR | 담당 고객 목록·검색, 전화번호·이메일로 등록 |
| `/instructor/schedule` | INSTRUCTOR | 시간 슬롯 추가·켜기/끄기·삭제 |
| `/instructor/posts` | INSTRUCTOR | 게시물 작성·수정·삭제, 미디어, 댓글 |
| `/instructor/notes` | INSTRUCTOR | 레슨노트 (글 · PDF) |
| `/instructor/revenue` | INSTRUCTOR | 결제 내역, 수동 등록 |
| `/instructor/insights` | INSTRUCTOR | 매출 분석 (월별·결제수단·수강권별) |
| `/instructor/promotions` | INSTRUCTOR | 할인·이벤트 프로모션 (프로토타입) |
| `/instructor/profile` | INSTRUCTOR | 강사 프로필, 정기 휴무 요일 |
| `/admin` | ADMIN | 관리자 대시보드 (강사 관리 · 시스템 관리 · 영업/통계는 준비 중) |
| `/schedule` | 인증 필요 | 스케줄 (기본 사이드바 메뉴) |
| `/forbidden` | — | 권한 없는 사용자 안내 |

---

## 인증·API 호출 구조

```
클라이언트 → Supabase Auth 로그인
          → /api/auth/sync (세션 쿠키 갱신)
          → src/proxy.ts 에서 로그인·역할 검사
          → /api/[...path] (Next.js 프록시) → FastAPI 백엔드
```

1. Supabase Auth 로그인 및 세션 발급
2. `/api/auth/sync`로 세션 쿠키 갱신
3. `src/proxy.ts`가 보호 경로의 로그인 여부를 확인하고, `/admin`·`/instructor`는 Supabase `users` 테이블의 역할로 검사 — 권한이 없으면 `/forbidden`
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
│   ├── (protected)/     # 로그인 필요 영역 (admin / instructor)
│   ├── schedule/        # 스케줄 (기본 사이드바 메뉴)
│   ├── login/           # 로그인
│   ├── forbidden/       # 권한 없음 안내
│   └── api/
│       ├── auth/sync/   # 세션 쿠키 갱신
│       └── [...path]/   # 백엔드 프록시
├── components/
│   ├── common/          # 준비 중 안내 등 공통 컴포넌트
│   └── layout/          # 대시보드 레이아웃 (사이드바·헤더)
├── lib/
│   ├── axios.ts         # API 클라이언트 (/api 프록시)
│   ├── date.ts          # 로컬 날짜 (YYYY-MM-DD)
│   └── supabase/        # Supabase 클라이언트 (client / server)
└── proxy.ts             # 접근 제어 (로그인·역할)
```