# 📄 CLAUDE.md

# 프로젝트: CRM_Core

골프 레슨 중심 CRM 시스템 (1인 개발, 모노레포)

구성:

* FastAPI 백엔드
* 관리자/강사용 웹 (Next.js)
* 고객용 모바일 앱 (Expo React Native)
* 강사용 모바일 앱 (Expo React Native)
* PostgreSQL (Supabase)
* 배포: 백엔드 AWS Copilot / 프론트엔드 Vercel

결제·회원권·수강권 등 **거래성 데이터**를 다루므로, 정확성과 구조적 규율을 최우선으로 한다.

---

# 0 작업 방식 (모든 세션 공통)

1. 세션 시작 시 `docs/progress.md`를 먼저 읽고 현재 단계를 파악한다.
2. 코드 수정 전 **영향 범위(파일·도메인·API 계약·DB)** 를 먼저 보고하고, 승인 후 진행한다.
3. **한 항목 = 한 브랜치 = 한 커밋(또는 PR)** 원칙. 여러 이슈를 한 변경에 섞지 않는다.
4. "고칠 필요 없음"도 정당한 결론이다. 불필요한 변경을 만들지 않는다.
5. 세션 종료 시 `docs/progress.md`에 완료 항목·다음 작업·미해결 이슈를 갱신한다.

---

# 1 리포지토리 구조

```text
CRM_Core/
├── backend/            # FastAPI 백엔드
├── frontend/           # 관리자/강사용 웹 (Next.js)
├── apps/customer/      # 고객 모바일 앱 (Expo)
├── apps/instructor/    # 강사 모바일 앱 (Expo)
├── packages/           # 공통 패키지 (api, ui — 현재 미구현, 예정)
├── docs/               # 운영 문서, 진행 현황(progress.md)
├── Makefile            # 주요 작업 진입점
└── CLAUDE.md
```

---

# 2 핵심 아키텍처 원칙 (절대 위반 금지)

## ✅ 백엔드

* FastAPI (async 기반) · SQLModel · PostgreSQL (AsyncPG) · Alembic
* 도메인 구조 강제

```text
backend/app/domains/{feature}/
  ├── models.py
  ├── schemas.py
  ├── router.py
  ├── repository.py
```

* router는 **요청 파싱 · 권한 확인 · 응답 변환만** 담당한다.
* 비즈니스 규칙과 상태 변경은 repository(도메인 계층)에 둔다.

### ❌ 절대 금지

* 도메인 간 로직 섞기
* router 또는 router 파일 내 helper 함수에 비즈니스 로직 작성
* sync DB 호출
* repository 레이어 우회
* 무단 마이그레이션 변경

## ✅ 상태 변경 범위 원칙 (재발 방지)

"특정 날짜/특정 건에 대한 조치"를 **전역 상태 변경으로 구현하지 않는다.**

* 예: 특정 날짜의 슬롯 마감을 `TimeSlot.is_active = false`로 처리하면 **모든 미래 날짜**에 적용된다 (실제 발생한 결함).
* 조치의 적용 범위(전역 / 기간 / 날짜 / 단건)를 먼저 정의하고, 그 범위를 표현하는 데이터 모델이 있는지 확인한다.
* 범위를 표현할 모델이 없으면 코드로 우회하지 말고 **모델 설계부터 제안**한다.
* UI 문구와 실제 API 효과의 범위가 일치하는지 반드시 확인한다.

## ✅ 프론트엔드 (Next.js)

* Next.js 16 (App Router) · React 19 · Tailwind CSS
* Zustand (클라이언트 상태) · TanStack Query (서버 상태)
* API는 반드시 `/api/[...path]` 프록시 경유

### ❌ 절대 금지

* 클라이언트에서 직접 백엔드 호출
* JWT를 localStorage에 직접 저장
* 백엔드 URL 하드코딩
* 인증 우회 코드 작성

## ✅ 모바일 앱 (Expo React Native — customer / instructor)

* Expo Router 사용
* Web과 동일한 API 계약 사용
* **현재 API 클라이언트는 각 앱의 `lib/api.ts`에 있다.** (`packages/api` 통합은 향후 과제)
* 응답 타입은 각 앱의 `types/api.ts`에 있으며, **백엔드 `schemas.py` 변경 시 두 앱의 타입을 함께 갱신**한다.
* 환경변수 파일은 **각 앱 폴더에 개별로** 둔다. Expo는 상위 폴더의 env 파일을 읽지 않는다.
* 클라이언트에 노출 가능한 값은 `EXPO_PUBLIC_` 접두사 변수만 사용한다.

### ❌ 절대 금지

* 한 앱 안에서 API 호출 로직 중복 작성 (반드시 `lib/api.ts` 경유)
* `packages/api` 통합을 요청 없이 임의 진행
* 환경변수 하드코딩
* 모바일 소스에 비밀키 저장 (service role key 등)

---

# 3 인증 구조

기본: Supabase JWT / 폴백: HS256 로컬 JWT

1. Supabase 로그인
2. 백엔드 JWT 검증
3. JIT 유저 생성 (최초 로그인 시, 백엔드에서만)
4. RBAC 권한 검증

### 역할(Role)

```text
CUSTOMER
INSTRUCTOR
CONTENT_MANAGER
ADMIN
```

### ❌ 절대 금지

* RBAC 체크 제거 · 역할 검증 무력화
* JWT 토큰 로그 출력
* 환경변수 노출

---

# 4 보안 정책 (매우 중요)

## 4.1 env 파일은 절대 읽지 말 것

아래 파일은 **열람/검색/출력/요약 금지**.

* `.env` · `.env.*` · `**/*.env` · `**/.env.*`

금지 범위: 직접 읽기, grep/ripgrep 검색, "일부만" 출력, 내용 기반 요약.

허용: 코드에서 참조하는 **환경변수 이름(KEY NAME)** 언급.
예: `SUPABASE_URL`, `DATABASE_URL`, `JWT_SECRET` — 단, **값(value)** 은 어떤 경우에도 출력/추측/재구성 금지.

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

* DB URL · JWT 내용 · AWS 키 · Supabase 서비스 키 출력
* 개인정보(이메일/전화번호 등) 덤프 출력

## 4.3 커밋 전 확인

* 새 env 파일이나 민감 파일을 만들 때는 **`.gitignore`에 포함되는지 먼저 확인**한다.
  (루트 `.gitignore`는 OS/에디터 파일만 다루고, env 규칙은 하위 폴더에만 있다.)
* `git add .` 대신 변경 파일을 명시적으로 추가한다.

## 4.4 사고 대응

* 즉시 해당 출력 공유 중단
* 노출 가능성이 있는 키는 폐기/재발급
* 커밋/PR/이슈에 남은 흔적은 즉시 제거 후 필요 시 히스토리 정리

---

# 5 수정 정책

코드 수정 시 반드시:

1. 요청된 범위만 수정
2. 관련 없는 파일 리팩토링 금지
3. async 패턴 유지
4. RBAC 무결성 유지

다음 항목 수정 시 **영향 분석 선행 후 승인**:

* 인증 로직 · 역할 체계 · JWT 구조 · Supabase 인증 방식
* DB 모델/스키마 · 마이그레이션
* API 계약 (백엔드 schemas ↔ 웹/두 모바일 앱 타입)
* 프록시 구조 · 도메인 구조 재배치

---

# 6 코딩 표준

## 백엔드

* async/await 필수 · 타입 명시
* 암묵적 commit 금지 (트랜잭션 경계 명확화)
* repository 패턴 유지
* 거래성 도메인(payment, membership, passes, booking)은 **변경 시 테스트 동반**
  → CI를 통과해도 런타임 논리 결함은 테스트로만 잡을 수 있다.

## 프론트엔드

* 서버 상태 TanStack Query / 클라이언트 상태 Zustand
* protected route는 Suspense 경계 유지
* 인증 로직은 중앙 관리

## 모바일

* Web과 동일한 API 계약 유지
* 플랫폼 분기 최소화

---

# 7 브랜치 · 배포 · 운영

## 7.1 브랜치 흐름

```text
작업 브랜치 → staging(기본 브랜치) → Release PR → main
```

* 기본 브랜치는 `staging`. 모든 PR은 staging 대상.
* main에 직접 커밋/PR 금지.
* 브랜치 이름: `fix/…`, `feat/…`, `refactor/…`, `docs/…`, `wip/…`
* 미완성 작업도 세션 종료 전 `wip/…` 브랜치로 푸시한다. (Codespace는 일정 기간 미사용 시 삭제됨)

## 7.2 환경

* local · staging · production

## 7.3 현재 운영 상태

* **AWS(백엔드 배포)는 현재 오프라인.** CI 검증 job은 정상 동작, deploy job은 실패가 예상된 상태.
* staging → main Release PR은 `make prtrigger`로 생성한다. 의미 있는 작업 단위 완료 시에만 실행.
* production 반영 전 실제 인프라에서 최소 1회 smoke test 필수.

## 7.4 절대 금지

* 배포 설정 임의 수정
* 환경변수 이름 변경
* 마이그레이션 이력 삭제
* CI 우회

---

# 8 로컬 검증 명령 (Makefile)

AWS 없이 로컬에서 먼저 검증한다.

```bash
make server        # 백엔드 로컬 서버
make check-db      # DB 연결 확인
make check-schema  # 모델 ↔ DB 스키마 확인
make tokens        # 테스트 토큰
make flow          # 주요 흐름 점검
make test          # 테스트
make verify        # 종합 검증
make prtrigger     # staging → main Release PR 생성
```

PR 전 최소 `make verify` 통과를 확인한다.

---

# 9 DB(마이그레이션) 안전 가이드

## 9.1 기본 원칙

* DB는 운영 자산, 마이그레이션은 변경 이력이다.
* 원격에 공유된 Alembic revision은 **불변**이다.

## 9.2 절대 금지

* 이미 공유/배포된 revision 파일 수정
* `alembic_version` 테이블 수동 조작
* 운영 DB에서 downgrade 강제
* migration 파일 삭제 후 기록 없는 재생성
* 데이터가 있는 컬럼의 무계획 타입 변경
* **승인 없이 원격 DB(Supabase)에 `alembic upgrade` 실행**

## 9.3 autogenerate 사용 규칙

* `alembic revision --autogenerate` 결과는 **그대로 커밋하지 않는다.** 생성된 op를 한 줄씩 검토한다.
* 의도하지 않은 인덱스/제약조건 drop·create가 섞여 있으면 **models.py 선언과 실제 DB가 어긋난 신호**다. 마이그레이션을 수정하지 말고 모델 선언부터 바로잡는다.
* 마이그레이션 작업 전 `alembic check`로 모델 ↔ DB 불일치 여부를 먼저 확인한다.

## 9.4 안전한 변경 순서

1. 모델 변경 (SQLModel)
2. 새 마이그레이션 생성 및 검토
3. 로컬/스테이징 업그레이드 테스트
4. 테스트(특히 smoke/booking) 통과 확인
5. PR/배포

## 9.5 데이터 보존 패턴

* 컬럼 추가: nullable 추가 → 데이터 채우기 → 필요 시 NOT NULL
* 타입 변경: 안전 캐스팅 확인, 위험 시 신규 컬럼 → 데이터 이전 → 구 컬럼 제거
* 이름 변경: 코드/API/테스트/앱 타입 영향과 하위 호환을 함께 검토

## 9.6 마이그레이션 PR 체크리스트

* 변경 테이블/컬럼 목록
* 롤백 가능 여부 + 이유
* 데이터 손실 가능성
* API 계약 영향 (웹 · customer · instructor)
* 스테이징 적용 테스트 결과

---

# 10 인증 흐름

## 10.1 Web (Next.js)

```text
[사용자] → [Supabase Auth] JWT 발급
  → [Next.js] /api/[...path] 프록시 (Authorization: Bearer 주입)
  → [FastAPI] JWT 검증 + Role 확인 + (최초) JIT 유저 생성
  → [Postgres]
```

## 10.2 Mobile (Expo)

```text
[사용자] → [Supabase Auth] JWT 발급
  → [Expo App] lib/api.ts (Authorization: Bearer 첨부)
  → [FastAPI] JWT 검증 + Role 확인 + (최초) JIT 유저 생성
  → [Postgres]
```

* 모바일은 프록시가 없으므로 `lib/api.ts`가 토큰을 직접 붙인다.
* Web/Mobile 모두 백엔드 검증 로직은 동일하다.

## 10.3 폴백 JWT(HS256)

* Supabase 검증 실패/비활성 시에만 발동하는 **긴급 대응 수단**이다.
* 발동 시 원인(형식/만료/키 불일치)을 구분해 로그를 남기고 재발 방지 조치를 한다.
* 상시 사용되는 상태로 만들지 않는다.

---

# 11 최종 목표

* 안정적인 FastAPI 백엔드
* 관리자 웹 완성
* 강사용 웹/앱 완성
* 고객용 모바일 앱 완성
* 안정적인 RBAC 체계
* 운영 단계에서 재발하지 않는 구조

단기 해결보다 장기 안정성 우선.