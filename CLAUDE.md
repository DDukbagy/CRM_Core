# 📄 CLAUDE.md

# 프로젝트: CRM_Core

골프 중심 CRM 시스템

구성:

* 관리자용 웹 (Next.js)
* 강사용 웹/앱 (확장 예정)
* 고객용 모바일 앱 (Expo React Native)
* FastAPI 백엔드
* PostgreSQL (Supabase)
* AWS Copilot 배포

모노레포 구조 기반 프로젝트.

---

# 1 리포지토리 구조

```text
CRM_Core/
├── backend/          # FastAPI 백엔드
├── frontend/         # 관리자 웹 (Next.js)
├── apps/customer/    # 고객 모바일 앱 (Expo)
├── packages/         # 공통 패키지 (API 유틸, 타입 등)
```

---

# 2 핵심 아키텍처 원칙 (절대 위반 금지)

## ✅ 백엔드 원칙

* FastAPI (async 기반)
* SQLModel
* PostgreSQL (AsyncPG)
* Alembic 마이그레이션
* 도메인 구조 강제

```text
backend/app/domains/{feature}/
  ├── models.py
  ├── schemas.py
  ├── router.py
  ├── repository.py
```

### ❌ 절대 금지

* 도메인 간 로직 섞기
* router에 비즈니스 로직 작성
* sync DB 호출
* repository 레이어 우회
* 무단 마이그레이션 변경

---

## ✅ 프론트엔드 (Next.js 관리자 웹)

* Next.js 16 (App Router)
* React 19
* Zustand (클라이언트 상태)
* TanStack Query (서버 상태)
* API는 반드시 `/api/[...path]` 프록시 경유

### ❌ 절대 금지

* 클라이언트에서 직접 백엔드 호출
* JWT를 localStorage에 직접 저장
* 백엔드 URL 하드코딩
* 인증 우회 코드 작성

---

## ✅ 모바일 앱 (Expo React Native)

* Expo Router 사용
* Web과 동일한 API 계약 사용
* `/packages` 내 공통 API 유틸 사용

### ❌ 절대 금지

* API 로직 중복 작성
* 환경변수 하드코딩
* 모바일 소스에 비밀키 저장

---

# 3 인증 구조

기본: Supabase JWT
폴백: HS256 로컬 JWT

인증 흐름:

1. Supabase 로그인
2. 백엔드 JWT 검증
3. JIT 유저 생성 (최초 로그인 시 자동 생성)
4. RBAC 권한 검증

### 역할(Role)

```text
CUSTOMER
INSTRUCTOR
CONTENT_MANAGER
ADMIN
```

### ❌ 절대 금지

* RBAC 체크 제거
* 역할 검증 무력화
* JWT 토큰 로그 출력
* 환경변수 노출

---

# 4 보안 정책 (매우 중요)

## 4.1 절대 규칙: env 파일은 절대 읽지 말 것

Claude Code 및 모든 자동화/에이전트/도구는 아래 파일을 **절대 열람/검색/출력/요약**하면 안 된다.

* `.env`
* `.env.*`
* `**/*.env`
* `**/.env.*`

### 금지 범위(명확화)

* 파일 내용을 직접 읽는 행위
* 파일을 검색(ripgrep/grep)해서 키/값을 확인하는 행위
* 디버깅 목적으로 `.env` 내용을 “일부만” 출력하는 행위
* `.env` 파일 내용을 기반으로 “설정이 뭐가 들어있다”라고 요약하는 행위

### 허용되는 범위(예외 아님)

* 코드에서 참조하는 **환경변수 이름(KEY NAME)** 을 언급하는 것
  예: `SUPABASE_URL`, `DATABASE_URL`, `JWT_SECRET`
* 단, **값(value)** 은 어떤 경우에도 출력/추측/재구성 금지

---

## 4.2 민감 파일 접근 금지 목록

```text
.env*
*.pem
*.key
id_rsa*
service-account*.json
credentials*.json
secrets.*
```

### 절대 금지 행위

* DB URL 출력
* JWT 내용 출력
* AWS 키 출력
* Supabase 서비스 키 노출
* 개인정보(이메일/전화번호 등) 덤프 출력

### 사고 대응 원칙(위반 발생 시)

* 즉시 해당 로그/출력 공유 중단
* 노출 가능성이 있는 키는 폐기/재발급
* 커밋/PR/이슈에 남은 흔적이 있으면 즉시 제거 후 히스토리 정리(필요 시)

---

# 5 수정 정책

코드 수정 시 반드시:

1. 요청된 범위만 수정
2. 관련 없는 파일 리팩토링 금지
3. 구조 변경 시 사전 영향 분석
4. async 패턴 유지
5. RBAC 무결성 유지

다음 항목을 수정할 경우 반드시 영향 분석 선행:

* 인증 로직
* DB 스키마
* 역할 체계
* API 계약
* 마이그레이션

---

# 6 코딩 표준

## 백엔드

* async/await 필수
* 타입 명시
* 암묵적 commit 금지
* repository 패턴 유지

## 프론트엔드

* 서버 상태는 TanStack Query
* 클라이언트 상태는 Zustand
* protected route는 Suspense 경계 유지
* 인증 로직은 중앙 관리

## 모바일

* Web과 동일한 API 계약 유지
* 공통 패키지 재사용
* 플랫폼 분기 최소화

---

# 7 배포 및 운영 원칙

환경:

* local
* staging
* production

절대 금지:

* 배포 설정 임의 수정
* 환경변수 이름 변경
* 마이그레이션 이력 삭제
* CI 우회

---

# 8 불확실할 때

다음 변경 전 반드시 설명 및 영향 분석:

* JWT 구조 변경
* Supabase 인증 방식 변경
* 프록시 구조 변경
* DB 모델 수정
* 도메인 구조 재배치

---

# 9 최종 목표

* 안정적인 FastAPI 백엔드
* 관리자 웹 완성
* 강사용 웹/앱 확장
* 고객용 모바일 앱 완성
* 안정적인 RBAC 체계
* 운영 단계에서 재발하지 않는 구조

단기 해결보다 장기 안정성 우선.

---

# 10 DB(마이그레이션) 안전 가이드

## 10.1 기본 원칙

* DB는 “운영 자산”이며, 마이그레이션은 “변경 이력”이다.
* CI 통과를 위해 마이그레이션을 임의로 지우거나 덮어쓰는 방식은 금지한다.
* Alembic revision은 “한 번 공유되면 절대 수정하지 않는다(불변)”가 기본 정책이다.

## 10.2 절대 금지

* 이미 원격에 공유/배포된 revision 파일 수정
* `alembic_version` 테이블을 수동으로 조작
* 운영 DB에서 downgrade 강제
* migration 파일 삭제 후 “기록 없는 재생성”으로 덮기
* 데이터가 있는 컬럼의 타입 변경을 무계획으로 수행

## 10.3 안전한 변경 순서(권장)

1. 모델 변경(SQLModel)
2. 새 마이그레이션 생성
3. 로컬/스테이징에서 업그레이드 테스트
4. 테스트(특히 smoke/booking) 통과 확인
5. PR/배포

## 10.4 데이터 보존이 필요한 변경 패턴

### 컬럼 추가

* nullable로 추가 → 데이터 채우기 → 필요시 NOT NULL 전환

### 컬럼 타입 변경

* 안전한 캐스팅 가능 여부 확인
* 위험 시 “신규 컬럼 추가 → 데이터 마이그레이션 → 구 컬럼 제거” 방식 사용

### 테이블/컬럼 이름 변경

* 단순 rename이 아니라 API/코드/테스트 영향이 크므로

  * 코드 변경 범위 + 마이그레이션 + 하위 호환 여부를 함께 검토한다.

## 10.5 운영 관점 체크리스트

마이그레이션 PR에 반드시 포함:

* 변경되는 테이블/컬럼 목록
* 롤백 가능 여부(가능/불가 + 이유)
* 데이터 손실 가능성(있음/없음)
* 기존 API 계약 영향(있음/없음)
* 스테이징 적용 테스트 결과

---

# 11 모바일-웹 인증 흐름 다이어그램

> 목적: “모바일/웹/백엔드”가 어떤 토큰을 어디서 받고, 어디서 검증하는지 혼동을 제거한다.
> 특히 프록시 구조와 JIT 유저 생성 위치를 명확히 한다.

## 11.1 Web (Next.js) 인증/요청 흐름

```text
[사용자]
   ↓ 로그인(클라이언트)
[Supabase Auth]
   ↓ JWT 발급(Access Token)
[Next.js Web]
   ↓ (프록시) /api/[...path]로 요청
[Next.js API Proxy]
   ↓ Authorization: Bearer <supabase_jwt> 자동 주입/전달
[FastAPI Backend]
   ↓ JWT 검증 + Role 확인
   ↓ (최초 로그인) JIT 유저 생성
[DB(Postgres)]
   ↑ 결과 반환
[Next.js Web]
```

핵심:

* Web은 백엔드를 직접 호출하지 않고, 프록시가 토큰을 붙여서 전달한다.
* JIT 유저 생성은 백엔드에서만 수행한다.

---

## 11.2 Mobile (Expo) 인증/요청 흐름

```text
[사용자]
   ↓ 로그인(앱)
[Supabase Auth]
   ↓ JWT 발급(Access Token)
[Expo App]
   ↓ API Client(공통 패키지)
   ↓ Authorization: Bearer <supabase_jwt>
[FastAPI Backend]
   ↓ JWT 검증 + Role 확인
   ↓ (최초 로그인) JIT 유저 생성
[DB(Postgres)]
   ↑ 결과 반환
[Expo App]
```

핵심:

* Mobile은 프록시가 없으므로 앱에서 API Client가 직접 토큰을 붙여서 호출한다.
* Web/Mobile 모두 백엔드 검증 로직은 동일해야 한다.

---

## 11.3 폴백 JWT(HS256) 위치

```text
(예외 상황)
Supabase 검증 실패/비활성 시
  → Backend가 HS256 로컬 JWT를 사용(폴백)
  → 단, 운영 정책상 "언제/왜 폴백이 발동되는지" 로그 레벨과 알림 정책이 필요
```

운영 원칙:

* 폴백은 “긴급 대응”이며, 무심코 상시 사용되면 보안/추적성이 급격히 떨어진다.
* 폴백 발동 시:

  * 원인(토큰 형식/만료/키 불일치) 구분
  * 재발 방지 조치 필요

---