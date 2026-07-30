# Customer App — 고객 모바일 앱 (Expo)

CRM Core의 고객용 모바일 앱입니다.
Expo + React Native + Expo Router + Supabase Auth 기반.
iOS·Android·Web(브라우저) 모두 지원합니다.

---

## Quick Start

```bash
cd apps/customer
npm install
npx expo start
```

터미널 출력에서 플랫폼을 선택합니다.
- `i` → iOS 시뮬레이터
- `a` → Android 에뮬레이터
- `w` → 웹 브라우저

---

## 환경변수

앱 루트에 `.env` 파일을 생성합니다.

```
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

> **참고**: Expo는 상위 디렉터리의 `.env`를 읽지 않습니다. 반드시 `apps/customer/.env`에 생성하세요.

---

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 프레임워크 | Expo SDK · React Native |
| 라우팅 | Expo Router (파일 기반) |
| 인증 | Supabase Auth (signInWithPassword) |
| 세션 유지 | AsyncStorage |
| API | 공통 `lib/api.ts` (Supabase 세션 토큰 자동 첨부) |
| 에러 트래킹 | Sentry (`@sentry/react-native`) |

---

## 앱 구조

```
app/
├── (auth)/          # 로그인·회원가입 (인증 없이 접근 가능)
│   └── login.tsx
├── (tabs)/          # 메인 탭 (인증 필요)
│   ├── index.tsx    # 홈 (오늘 예약)
│   ├── schedule.tsx # 스케줄 (강사 슬롯 + 예약 신청)
│   ├── bookings.tsx # 내 예약 목록 + 취소/철회
│   ├── match.tsx    # 강사 매칭·상담 신청
│   ├── chat.tsx     # 강사 채팅 (모임 채팅 준비 중)
│   ├── passes.tsx   # 수강권 현황·갱신
│   └── profile.tsx  # 내 정보·로그아웃
└── _layout.tsx      # 인증 상태 → 라우팅 제어

lib/
├── supabase.ts      # Supabase 클라이언트 (AsyncStorage 세션)
└── api.ts           # API 클라이언트 (토큰 자동 첨부)

types/
└── api.ts           # API 응답 타입 정의
```

---

## 주요 기능

| 기능 | 내용 |
|------|------|
| 예약 | 강사 가용 슬롯 조회 → 예약 신청 → 취소/철회 |
| 매칭 | 강사 목록 조회 · 검색 → MATCH·CONSULTATION 요청 |
| 채팅 | 담당 강사와 1:1 채팅 |
| 수강권 | 레슨 패스 현황·사용 이력·갱신 요청 |
| 멤버십 | 횟수제(TIMES) / 기간제(PERIOD) 현황 |
| 내 정보 | 프로필 확인 및 로그아웃 |