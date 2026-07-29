# Instructor App — 강사 모바일 앱 (Expo)

CRM Core의 강사용 모바일 앱입니다.
Expo + React Native + Expo Router + Supabase Auth 기반.
iOS·Android·Web(브라우저) 모두 지원합니다.

---

## Quick Start

```bash
cd apps/instructor
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

> **참고**: Expo는 상위 디렉터리의 `.env`를 읽지 않습니다. 반드시 `apps/instructor/.env`에 생성하세요.

---

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 프레임워크 | Expo SDK 54 · React Native |
| 라우팅 | Expo Router (파일 기반) |
| 인증 | Supabase Auth |
| 보안 저장소 | expo-secure-store |
| 미디어 | expo-image-picker · expo-video (게시물 사진·동영상 첨부) |
| 캘린더 | react-native-calendars |
| 에러 트래킹 | Sentry (`@sentry/react-native`) |

---

## 앱 구조

```
app/
├── (tabs)/            # 메인 탭 (인증 필요)
│   ├── index.tsx      # 대시보드
│   ├── customers.tsx  # 고객 관리 (이메일로 담당 고객 등록)
│   ├── schedule.tsx   # 스케줄 (타임슬롯 활성화 · 예약 승인/관리)
│   ├── chat.tsx       # 채팅
│   ├── posts.tsx      # 글쓰기 (사진·동영상 첨부 게시물)
│   ├── revenue.tsx    # 매출
│   └── profile.tsx    # 내 정보 (강사 프로필 · 정기 휴무 요일)
└── _layout.tsx        # 인증 상태 → 라우팅 제어

lib/
└── api.ts             # API 클라이언트 (토큰 자동 첨부)

types/
└── api.ts             # API 응답 타입 정의
```

---

## 주요 기능

| 기능 | 내용 |
|------|------|
| 대시보드 | 오늘 일정·주요 현황 요약 |
| 고객 관리 | 담당 고객 목록 · 검색 · 이메일로 신규 등록 |
| 스케줄 | 타임슬롯 활성화/비활성화 · 예약 요청 승인 · 취소/노쇼 처리 |
| 채팅 | 담당 고객과 1:1 채팅 |
| 게시물 | 프로모션·고객 피드백 작성 · 사진/동영상 첨부 (S3 업로드) |
| 매출 | 결제·매출 현황 조회 |
| 내 정보 | 강사 프로필 편집 (활동 지역·전문 분야·경력·자격증) · 정기 휴무 요일 설정 |