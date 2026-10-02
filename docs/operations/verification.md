# 실제 환경 검증 (Supabase 로그인 · 전체 흐름 · 앱 로그인 · S3)

로컬 검증(`make check`, `make apiverify`)은 로컬 DB와 직접 서명한 토큰으로만 확인한다.
아래는 **실제 Supabase 계정·자격 증명**이 있어야 확인할 수 있는 것들이다.

> 토큰·env 값은 **본인 VS Code 터미널에서만** 다룬다. Claude 대화창(`!` 명령 포함)에 붙여넣거나 출력하지 않는다.
> 서버 로그에도 토큰 일부가 섞일 수 있으므로 로그 원문을 공유하지 않고 "몇 번 단계에서 몇 코드가 났다"만 공유한다.
> 이 문서의 명령은 `backend/.env` 의 **원격 Supabase DB** 를 사용한다. 데이터가 실제로 생긴다.

## 진행 현황

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 준비: env 파일, 백엔드 실행 | ✅ |
| 1 | 고객 계정 토큰 → `/auth/me` | ✅ 2026-10-02 `200`, role CUSTOMER |
| 2 | 강사 계정 토큰 (필요하면 신청·승인) | ✅ 2026-10-02 승인된 강사 |
| 3 | 전체 흐름 `make apiflow` (14단계) | ✅ 2026-10-02 `FLOW TEST DONE` (예약 #4 생성→중복 409→철회, 원격 DB 에 철회 상태로 남음) |
| 4 | 두 앱에서 실제 로그인 | ✅ 2026-10-02 고객 앱·강사 앱 로그인·로그아웃, 역할 차단(강사 앱에 고객 계정 / 고객 앱에 강사 계정 → 둘 다 막힘) |
| 4-1 | 앱 화면별 확인 (아래 표) | ⬜ **다음** |
| 5 | 웹에서 실제 로그인 (선택) | ⬜ |
| 6 | S3 업로드 (AWS 필요, 선택) | ⬜ |

---

## 0. 준비

### env 파일 (각 폴더에 따로 둔다. git 에 올라가지 않음)

| 파일 | 변수 | 값을 찾는 곳 |
|---|---|---|
| `backend/.env` | `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `SUPER_ADMIN_EMAIL` 등 | 이미 있음 |
| `apps/customer/.env`, `apps/instructor/.env` | `EXPO_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → Data API(또는 API) → **Project URL** |
| | `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Project Settings → API Keys → **anon / public** (또는 Publishable key). ⚠️ service_role·Secret key 는 절대 넣지 않는다 |
| | `EXPO_PUBLIC_API_BASE_URL` | 백엔드 주소 (아래 표) |
| `frontend/.env.local` (5단계 할 때) | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 위와 같은 값 |
| | `API_BASE_URL` | `http://localhost:8000` (웹은 서버가 대신 호출) |

예시 파일에서 복사해 값만 채운다: `cp apps/customer/.env.example apps/customer/.env` (instructor·frontend 도 같은 방식)

`EXPO_PUBLIC_API_BASE_URL`:

| 앱을 여는 곳 | 값 |
|---|---|
| Codespace 안 브라우저 | `http://localhost:8000` |
| 내 PC 브라우저·실기기 | VS Code **포트** 탭의 8000 주소 `https://<codespace>-8000.app.github.dev` (끝 `/` 없이). 8000 포트를 오른쪽 클릭 → 포트 공개 범위 → **Public**. 테스트가 끝나면 Private 으로 되돌린다 |

env 를 바꾸면 앱을 껐다가 다시 켜야 반영된다.

### 백엔드 실행

```bash
make api          # 터미널 1. "Application startup complete." 가 보이면 준비 완료
```

다른 터미널에서 확인:

```bash
curl -s -w ' [%{http_code}]\n' http://127.0.0.1:8000/health     # [200] 이어야 함
```

`[000]` 이면 백엔드가 꺼진 것 → 터미널 1 을 확인하고 `make api` 다시 실행.

### 테스트 계정

이미 있는 계정을 써도 된다. 이메일 인증이 된 계정이어야 한다. 확인 방법 (대시보드 버전마다 표시가 다름):

- 가장 확실한 방법: `make apitoken` 을 실행해 토큰이 나오면 인증된 계정. `Email not confirmed` 가 나오면 미인증
- Supabase → Authentication → Users 목록에 "Waiting for verification" 표시가 있으면 미인증
- 미인증이면 계정 상세 → 메뉴(⋯) → Confirm user

User ID = Users 목록의 **UID** (`make apitoken` 출력의 "[1] User ID" 와 같은 값, 우리 DB 회원 id 와 같음).

필요한 계정:

- 고객 계정 1개
- 강사 계정 1개
- 관리자: `backend/.env` 의 `SUPER_ADMIN_EMAIL` 로 지정한 이메일 계정 (로그인하면 자동으로 ADMIN) — 강사 승인이 필요할 때만

---

## 1. 고객 토큰 검증 ✅

```bash
make apitoken                       # 고객 계정 이메일·비밀번호 → User ID, Access Token 출력
export GUEST_TOKEN='<고객 Access Token>'
curl -s -w ' [%{http_code}]\n' -H "Authorization: Bearer $GUEST_TOKEN" http://127.0.0.1:8000/auth/me
```

| 결과 | 의미 |
|---|---|
| `[200]` + `"role": ...` | 성공. 첫 로그인이면 회원이 자동 생성됨 |
| `[000]` | 백엔드 꺼짐 → 0 단계 |
| `401` + `Token expired` | 토큰 만료(약 1시간) → `make apitoken` 다시 |
| `401` (그 외) | 검증 실패. 터미널 1 로그에 `local jwt verify` 가 보이면 Supabase 검증 실패 후 폴백까지 간 것 → 발급자·대상·비밀값 설정 확인 (`SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` 는 기본값과 다를 때만 지정) |
| `403` "탈퇴한 계정입니다" | 탈퇴 처리된 계정 |
| `409` | 같은 이메일이 다른 계정으로 이미 있음 |
| apitoken 에서 `Email not confirmed` | Supabase 에서 Confirm user |

## 2. 강사 토큰

```bash
make apitoken                       # 강사 계정
export HOST_TOKEN='<강사 Access Token>'
export HOST_ID='<강사 User ID>'   # ⚠️ 고객 User ID 와 헷갈리지 않게. 틀리면 3 단계 8) availability 가 404
curl -s -w ' [%{http_code}]\n' -H "Authorization: Bearer $HOST_TOKEN" http://127.0.0.1:8000/auth/me
```

응답의 `role`·`status` 에 따라:

| 응답 | 다음 |
|---|---|
| `INSTRUCTOR` + `ACTIVE` | 3 단계로 |
| `INSTRUCTOR` + `PENDING` | 아래 "승인" |
| `CUSTOMER` | 아래 "신청" → "승인" |

신청 (`CUSTOMER` 인 계정만. 이미 강사·관리자인 계정은 `403 Insufficient role` 이 정상):

```bash
curl -s -X POST -w ' [%{http_code}]\n' -H "Authorization: Bearer $HOST_TOKEN" http://127.0.0.1:8000/instructors/apply
```

승인 (관리자 계정으로):

```bash
make apitoken                       # SUPER_ADMIN_EMAIL 계정
export ADMIN_TOKEN='<관리자 Access Token>'
curl -s -X POST -w ' [%{http_code}]\n' -H "Authorization: Bearer $ADMIN_TOKEN" http://127.0.0.1:8000/instructors/$HOST_ID/approve
```

`[200]` 이면 승인 + 기본 캘린더(매일 07~20시 1시간 슬롯 13개) 자동 생성. `/auth/me` 를 다시 호출해 `ACTIVE` 확인.

## 3. 전체 흐름 (14단계)

1·2 단계의 `GUEST_TOKEN`, `HOST_TOKEN`, `HOST_ID` 를 export 한 같은 터미널에서:

```bash
BASE_URL=http://127.0.0.1:8000 make apiflow
```

- 캘린더·슬롯 확인 → 가용 시간 → 예약 신청 → 강사 목록 확인 → 철회 등 14단계
- 마지막에 `FLOW TEST DONE ✅` 가 나오면 성공. 실패하면 "몇 번째 단계, 몇 코드" 만 공유
- 토큰 만료(401)가 나오면 1·2 단계의 `make apitoken` 만 다시 하고 export
- ⚠️ 원격 DB 에 테스트 예약이 남는다 (철회 상태)

## 4. 두 앱에서 실제 로그인

```bash
make cweb         # 고객 앱 → 고객 계정으로 로그인
make iweb         # 강사 앱(8082) → 강사 계정으로 로그인
```

확인할 것 (화면만):

| 앱 | 화면 | 기대 |
|---|---|---|
| 고객 | 홈 | 인사말에 내 이름, 오늘·이번 주 예약 |
| 고객 | 달력 | 강사의 정기 휴무일 "정기휴무", 예약 가능한 날 파란 점 |
| 고객 | 내 정보 | 이메일·전화번호, 아래쪽 "회원 탈퇴" 버튼 (누르지 말 것 — 실제로 탈퇴됨) |
| 강사 | 대시보드 | 신청 관리·오늘 예약 (3 단계 예약이 철회 상태면 목록에 없음) |
| 강사 | 스케줄 | 이번 달 달력, 날짜 눌러 시간대 패널 |
| 강사 | 채팅·매출·내 정보 | 오류 없이 열림 |

| 증상 | 원인 |
|---|---|
| 요청이 404, 백엔드 로그에 `path=//users/me` 처럼 `/` 두 개 | `EXPO_PUBLIC_API_BASE_URL` 끝의 `/` (2026-10-02 앱이 자동으로 떼도록 수정) |
| 브라우저에서 확인창이 필요한 버튼(로그아웃 등)이 반응 없음 | 앱의 `Alert.alert` 는 웹에서 아무것도 띄우지 않음. 로그아웃은 2026-10-02 수정, 나머지 5개 버튼은 수정 대기 (폰에서는 정상) |
| 로그인 실패 | `EXPO_PUBLIC_SUPABASE_URL`/`ANON_KEY` 값 또는 앱 재시작 안 함 |
| 로그인은 되는데 데이터가 비어 있음·오류 | `EXPO_PUBLIC_API_BASE_URL` (내 PC 브라우저면 8000 포트 Public 인지, 끝 `/` 없는지) |
| 강사 앱 로그인 후 "승인 대기" 류 오류 | 2 단계 승인 안 됨 |

## 5. 웹에서 실제 로그인 (선택)

```bash
make web          # http://localhost:3000/login
```

- 강사 계정 → `/instructor` 대시보드. 고객 계정 → "일반 회원은 관리자 웹페이지에 접속할 수 없습니다" (정상 차단)
- 관리자(`SUPER_ADMIN_EMAIL`) → `/admin` (강사 관리·시스템 관리·영업/통계는 "준비 중")
- 웹은 로그인 후 역할을 Supabase 의 `users` 테이블에서 직접 읽는다(본인 행 RLS 정책). 로그인은 되는데 `ROLE_UNAVAILABLE` 로 돌아오면 이 정책 문제

---

## 6. S3 미디어 업로드 · 조회 · 삭제 (AWS 필요, 선택)

목적: 게시물 사진·영상이 비공개 버킷에 올라가고, 서명 주소로만 보이고, 게시물 삭제 시 함께 지워지는지 확인한다.

### 준비 (AWS)

1. **S3 버킷**: 리전 `ap-northeast-2`, **Block all public access 켜기** (비공개 버킷 결정)
2. **IAM 액세스 키**: 이 버킷에만 `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
3. **버킷 CORS**: 앱이 서명 주소로 직접 올리므로 `PUT`, `GET` / 헤더 `Content-Type` / 개발 주소(Origin) 허용
4. `backend/.env`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME` → `make api` 재시작

### 진행

2 단계에서 export 한 **강사 토큰**(`HOST_TOKEN`)을 쓴다.

```bash
API=http://127.0.0.1:8000
AUTH="Authorization: Bearer $HOST_TOKEN"

# 1) 업로드 주소 받기 → upload_url, public_url
curl -s -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"filename":"t.jpg","content_type":"image/jpeg"}' $API/posts/upload-url

# 2) 업로드 (200 이어야 함)
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H "Content-Type: image/jpeg" --data-binary @t.jpg "<upload_url>"

# 3) 게시물 만들기 → 응답의 media_items[0].url 이 서명 주소
curl -s -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"type":"NOTICE","title":"S3 검증","media_items":[{"url":"<public_url>","media_type":"IMAGE"}]}' $API/posts

# 4) 서명 주소는 200, 서명 없는 public_url 은 403 이어야 함 (= 비공개 버킷)
curl -s -o /dev/null -w '%{http_code}\n' "<응답의 서명 주소>"
curl -s -o /dev/null -w '%{http_code}\n' "<public_url>"

# 5) 게시물 삭제(204) 뒤 같은 서명 주소가 실패해야 함 (= S3 객체도 삭제됨)
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE -H "$AUTH" $API/posts/<게시물 id>
curl -s -o /dev/null -w '%{http_code}\n' "<응답의 서명 주소>"
```

6) 마지막으로 강사 앱에서 사진을 첨부해 글을 쓰고, 고객 앱에서 보이는지 확인한다.

| 단계 | 기대값 | 다르면 |
|---|---|---|
| 1 | 200 | 500 이면 AWS 값 누락(`AWS credentials or bucket name missing` 로그) |
| 2 | 200 | 403 이면 IAM 권한·서명 만료(5분), CORS 는 앱에서만 문제됨 |
| 4 | 200 / 403 | public_url 이 200 이면 버킷이 공개 상태 |
| 5 | 204 / 403·404 | 계속 200 이면 객체가 남음 → 로그의 `S3 delete failed` 확인 |
