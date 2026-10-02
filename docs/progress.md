# 진행 현황 (CRM_Core)

> 세션 시작 시 이 파일을 먼저 읽는다. 세션 종료 시 "현재 단계", "다음 작업", "결정 대기"를 갱신한다.
> 규칙(무엇을 지켜야 하는가)은 CLAUDE.md, 상태(어디까지 했는가)는 이 파일에 둔다.

---

## 1. 프로젝트 목표 (사용자 기준)

1. 이 프로젝트는 포트폴리오의 **주력**이다. 구조가 잘 정리되어 있어야 하고, **사용자 본인이 그 정리를 이해하고 설명할 수 있어야** 한다.
2. 최우선 가치는 **일관성과 가독성**이다.
   - 가독성 = 저장소를 처음 연 사람이 **폴더명·파일명·구조만 보고** 역할을 이해할 수 있는 상태
   - Makefile 타깃 이름 같은 세부 표기는 현재 우선순위가 아니다.
3. 진행 순서: 폴더 구조 파악 → 폴더 구조 정리 → 프로젝트 전체 일관성 정리(CLAUDE.md 포함) → 분석·마무리 → 포트폴리오 정리·배포

---

## 2. 협업 방식 (Claude Code가 지킬 것)

사용자는 이 저장소의 설계 판단을 Claude Code 안에서 함께 내린다. Claude Code는 실행자이면서 **설계 컨설턴트** 역할을 겸한다.

1. 결함을 보고할 때 **심각도와 작업 순서를 구분**한다. 🔴라도 로직 변경이면 5단계에서 다루고, 이후 단계를 막거나 정리 중에도 피해를 만드는 항목만 앞으로 당긴다.
2. 선택지가 있는 결정은 대신 내리지 않는다. **선택지 · 각각의 장단점 · 권장안과 이유**를 제시하고 사용자가 고른다.
3. 결정이 나면 그 **이유를 한두 줄로 남긴다**(이 파일 §6 또는 `docs/decisions/`). 포트폴리오 설명 자료로 쓴다.
4. 사용자가 이해하지 못한 채 구조가 바뀌지 않도록, 변경 전 "무엇을, 왜"를 짧게 설명한다.
5. 조사 결과는 가능하면 **답변으로** 준다. 결정의 입력이 되는 큰 조사만 `docs/audit/`에 쓴다. `docs/audit/`는 작업용 자료이며 커밋하지 않는다(사용자 지시). 구조 파악이 끝나면 최종 구조 문서와 결정 기록으로 흡수하고 지운다.
6. 코드 이동 커밋과 내용 수정 커밋은 분리한다(파일 이력 보존, 리뷰 가능성).
7. 세션이 길어지면 결과를 이 파일에 반영한 뒤 `/clear` 하도록 사용자에게 제안한다.

---

## 3. 로드맵

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 기반·안전: ~~env 복구~~, ~~sync job 제거~~(배포 재개 시), ~~루트 .gitignore 보강~~, ~~`make grep` env 제외~~, ~~devcontainer Node~~ | ✅ (2026-10-01) sync job 만 배포 재개 시 |
| 1 | 구조 파악 | 🟡 진행 중 |
| 2 | 목표 구조·명명 규칙 확정 (사용자 결정) | ⬜ |
| 3 | 구조 정리 (이동·이름 변경·잔재 삭제만, 로직 변경 없음) | ⬜ |
| 4 | 일관성 정리: CLAUDE.md, README 4종, 운영 문서를 실제 구조에 맞춤 | ⬜ |
| 5 | 분석·마무리: 결함 수정, 테스트, repository 전환 | ✅ (2026-10-01) 결함 수정·테스트 보완·repository 전환 완료 |
| 6 | 포트폴리오 정리·배포 | ⬜ |

1~4단계 동안 지킬 것:
- DB 모델(`models.py`)과 마이그레이션 파일은 이동·수정하지 않는다.
- ~~캘린더 Phase 0–1 해결 전까지 `alembic revision --autogenerate` 실행 금지.~~ (2026-10-01 인덱스 불일치 해소, `alembic check` 통과. autogenerate 결과는 여전히 한 줄씩 검토)

---

## 4. 현재 단계: 1단계 구조 파악

### 완료 (`docs/audit/`, 커밋하지 않는 작업용 자료)
- `00-root.md`: .gitignore, workflows, Makefile, 문서 불일치
- `01-backend-map.md`: 도메인 목록·줄 수·도메인 간 import, alembic, verify, 테스트
- `05-local-files.md`: Codespace 삭제로 사라진 로컬 파일과 env 변수 목록

### backend 점검 완료 (2026-09-27)
- 원칙 위반 수정: `security.py`, `health.py` → `core/` 하위, users router 내 스키마 → `schemas.py`. `backend/aws/` 삭제
- 남은 결정은 §6, 결함은 §7 참고

### backend 도메인 재편 진행 (2026-09-30~)
목적(사용자): 도메인을 보기 좋게 정리. 독립이 맞는 것은 독립 도메인으로, 세부 기능이 맞는 것은 부모 도메인 안으로. 무조건 쪼개지 않는다.
- 독립 기준: 자체 테이블·상태 흐름·규칙이 있음 / 여러 도메인이 함께 사용 / 혼자 설명 가능
- 세부 기능 기준: 부모 없이는 의미 없음 / 부모 테이블에 매달림 / 부모와 함께 바뀜
- 미판단 2건 결정(2026-10-01): calendar의 예약 분리는 5단계로(D7), 로그인 API는 `auth`로 이동 완료(D8)
검증 방법: 이동 전후 경로·테이블 정의 스냅샷 비교, 빈 로컬 DB에 `alembic upgrade head`, pytest
- ✅ `lesson_notes` 분리: `calendar/lesson_note_*` → `lesson_notes/{models,schemas,router}.py`. 경로 113개·테이블 24개 정의 동일, 테스트 35개 통과
- ✅ `matching` 분리: instructor의 매칭 경로 5개·`MatchRequest` 모델·스키마 2개 → `matching/{models,schemas,router}.py`. API 경로 `/instructors/match…` 유지. `NAMED_FEE`는 `matching/models.py`에 두고 instructor가 import. 스냅샷 동일, 테스트 35개 통과(매칭 테스트 10개 포함)
- ✅ `notifications` 분리: posts의 `Notification` 모델·알림 종류·경로 2개·스키마·repository 메서드 3개 → `notifications/{models,schemas,router,repository}.py`. posts repository가 같은 세션으로 `NotificationRepository`를 호출(트랜잭션 공유). `app/db/models.py`에 등록 추가. 스냅샷 동일, 테스트 35개 통과, 댓글·좋아요 → 알림 생성·읽음 처리 직접 확인
- ✅ `booking` 분리 (2026-10-01, D7): 휴무 재설계로 예약 테이블에 레슨만 남은 뒤 `calendar` 의 `Booking` 모델·예약 스키마·`BookingRepository`·예약 경로 18개 → `booking/{models,schemas,repository,router}.py`. API 경로 그대로(강사 `/calendars/me/bookings…`, 고객 `/bookings…`), 캘린더+예약 경로 29개 동일. 의존 방향은 booking → calendar 한쪽(예약 생성이 `CalendarBlockRepository.day_status_for` 로 휴무 규칙 확인). 가려져 쓰이지 않던 옛 블록 스키마(날짜 범위형) 정의 삭제. 테스트 175개·`make check`·`make apiverify` 통과
- ✅ posts + content 병합 (2026-09-30): `content/` 폴더 제거, `posts/{models,schemas,router,repository}.py`로 통합. 경로 113 → 103개, 모델 테이블 24 → 20개(예전 5개는 DB에 `legacy_`로 보관)
  - 마이그레이션 `l6m7n8o9p0q1_merge_posts_and_content`: 테이블 이름 변경 + 컬럼 추가 + FK 정리. 데이터 삭제 없음, downgrade 가능
  - 검증: ① 빈 DB 전체 적용 ② 기존 DB 재현본(양쪽 테이블에 시험 데이터)에 적용 → 게시물·미디어·댓글 보존, 예전 데이터는 `legacy_*`에 보존 ③ downgrade → 재upgrade ④ pytest 51개 통과(게시물 14개 신규, 공개 동의 6개) ⑤ 웹 tsc·eslint, 두 앱 tsc
  - 추가 검증(2026-09-30, 서버 직접 호출): 로컬 DB에 서버를 띄우고 실제 HTTP로 142건 호출 → 139건 통과. 토큰 검증(Supabase HS256 형식·폴백)·유저 자동 생성·관리자 승격·강사 신청/승인·게시물 전 기능·알림·commit 후 DB 상태·재시작 후 유지 확인. 실패 3건은 모두 이번 재편과 무관한 기존 결함(§7 "서버 직접 호출로 발견"). 미검증: 실제 Supabase 로그인(RS256/JWKS), S3 실제 업로드·삭제, 웹·앱 화면, 원격 DB
  - 규칙 위치: 작성 권한·종류별 공개 여부·피드백 동의·댓글 권한은 `posts/repository.py`. router는 요청·응답 변환만
  - 동작이 달라진 점: 공개 게시물은 다른 강사·비로그인도 상세 조회 가능(예전 content는 강사가 남의 글을 못 봄). 콘텐츠 매니저는 공개 글과 본인이 작성한 글만 조회(예전 content는 제한 없음). 댓글·좋아요 시 게시물 주인에게 알림
  - **남은 일**: 원격 DB에 마이그레이션 적용(승인 필요, `l6m7n8o9p0q1`·`m7n8o9p0q1r2`·`n8o9p0q1r2s3` 3개) 전 `legacy_*` 대상 테이블의 실제 데이터 확인 / S3 버킷 비공개 전환(지금은 공개 버킷이어도 동작) / 웹·앱에 좋아요·대댓글·댓글 수정·공지·커뮤니티 화면 없음 / ~~`scripts/reset_db.py` 실행 불가(D3)~~ 2026-10-01 재작성
  - 설계 결정 기록:
  - 결정(2026-09-30): 게시물 종류는 공지·홍보·피드백·모임 매칭을 우선 구현
  - 결정(2026-09-30): 공개 범위는 전체 공개 / 비공개 2가지 + 피드백 공개 동의 유지. "회원만(MEMBERS)"은 미구현 값이라 제거. 공지·홍보는 공개, 피드백은 비공개(강사·지정 고객)로 시작
  - 결정(2026-09-30): 미디어 조회는 임시 서명 주소로 통일(비공개 버킷). 업로드는 앱이 직접 올리는 방식 유지. 이유: 비공개 피드백 영상의 주소가 공개되면 안 됨
  - 결정(2026-09-30): 댓글 ID는 정수 유지(앱 타입 변경 없음). 조건: 모든 댓글 경로에서 게시물 접근 권한·작성자 확인
  - 결정(2026-09-30): API 경로는 `/posts` 한 벌로 통일. 웹·두 앱의 `/instructor-posts` 호출 18곳을 함께 수정. 이유: 폴더·주소·내용의 이름 일치, 배포 중단 중이라 변경 비용이 가장 낮은 시점
  - 결정(2026-09-30, 앞 결정 변경): 게시물 종류는 홍보·공지·피드백·커뮤니티 4종. 모임 매칭은 게시물 종류가 아님
  - 결정(2026-09-30, 앞 결정 변경): 모임 찾기는 posts가 아니라 `matching` 도메인의 기능. matching = 강사 찾기(강사 매칭) + 모임 찾기. 게시물에 신청하는 방식이 아니라 독립된 카테고리
  - 결정(2026-09-30): posts의 게시물 참가 매칭 초안(`/match/*` 경로 3개, `match_requests`, 게시물의 슬롯·날짜 필드)은 병합 때 빼고, 모임 찾기는 matching에서 새로 설계. 이유: 초안은 게시물에 매달린 구조라 새 개념과 맞지 않고 결함 2건 포함, 앱 호출 없음. 코드는 git 이력(`76fdfb4` 이전)에 남음
  - 결정(2026-09-30): 기준은 content 쪽 테이블. `instructor_posts`→`posts`, `instructor_post_media`→`post_media`, `post_comments` 유지, `post_likes` 신설. 예전 posts 쪽 테이블 5개는 `legacy_` 접두사로 보관(데이터 복사 없음, 원격 데이터 확인 후 판단)
  - 결정(2026-09-30): 피드백 공개 동의·철회는 피드백 대상 고객이 함. 이유: 고객 본인의 레슨 영상
  - 결정(2026-09-30): 글 작성 권한은 지금처럼 강사·콘텐츠 매니저·관리자. 고객의 커뮤니티 글 작성은 병합 이후 별도 기능
  - 범위: 앱은 주소만 `/posts`로 변경. 좋아요 등 새 화면은 별도 작업
  - 구현 예정(matching): 모임 찾기 — 모집 인원·마감·신청·취소·모임 채팅
- ✅ 잔여 정리 (2026-10-01)
  - 문서 위치(D6): `backend/Docs/` 3개 → `docs/operations/`, 루트 `CRM_Requirements_v1.0.html` → `docs/requirements/`. 루트·backend README 링크 갱신. 문서 내용은 4단계에서 수정
  - 모델 등록: 목록을 `app/db/models.py` 한 곳으로 모으고 `alembic/env.py`는 이 파일만 import. 마이그레이션 시점 모델 테이블 16개 동일, 빈 DB `upgrade head` 스키마 덤프 동일, `alembic check`는 캘린더 인덱스 1건만(기존)
    - passes, chat은 등록하지 않음(파일에 이유 기록). 등록하면 init의 `create_all`이 chat 테이블을 먼저 만들어 `k5l6m7n8o9p0`이 `DuplicateTable`로 실패함(실험으로 확인). 두 도메인의 모델 변경은 여전히 alembic이 감지 못 함 → 5단계 과제
  - `scripts/`:
    - `seed_dev_data.sql`: 게시물 부분이 병합 전 posts 구조(`owner_user_id`, `caption`, `post_type`, `status` …)를 써서 실행 실패 → **posts 병합으로 생긴 문제**. 새 구조로 수정, 고객 없는 공개 FEEDBACK 1건은 COMMUNITY로. 롤백 트랜잭션에서 전체 실행 확인
    - `check_schema.py`: 병합 전 posts 컬럼(`is_consent_given` 등)만 확인해 거짓 경고 → **병합으로 생긴 문제**. 등록된 모델 전체(+ passes·chat)와 DB 컬럼을 비교하도록 재작성
    - `run_flow.sh`: 없는 `/accounts` 경로 → `/users`, 확정 전 예약 취소를 `/cancel` → `/withdraw`(취소 요청 흐름 도입 후 바뀐 규칙). 로컬 서버에서 14단계 전부 통과
    - `verify.sh`: 기준 폴더를 저장소 루트 → `backend/`. 서버 자동 실행까지 동작, 토큰 단계는 D5 대기. `KEEP_SERVER=0`이어도 uvicorn 자식 프로세스가 남는 문제 발견(5단계)
    - `reset_db.py`(D3 결정): 예전 comments 초기화용 일회성 스크립트 → 로컬 전용 초기화로 재작성(호스트가 localhost가 아니면 거부, DB 이름 입력 확인, public 스키마 비움 → `alembic upgrade head`). Makefile 설명 갱신
    - `check_db_connection.py`, `get_token.sh`, `install_aws_tools.sh`, `smoke_booking.sh`: 경로·엔드포인트 확인, 변경 없음

### ✅ 실제 화면 점검 (2026-10-02) → `docs/audit/03-runtime-check.md`. 로컬 스택 + 가짜 Supabase 인증 + Playwright, 화면 52개. 결함 6건 수정·재확인(UTC 날짜 27곳, 채팅 9시간, 웹 메뉴 선택, 게시글 배지, 탈퇴 버튼 가림, 옛 스케줄 요일)

### ✅ 프론트 점검 (2026-10-02) → `docs/audit/02-frontend-apps.md`. API 호출 103개 전부 백엔드와 일치, 참조 없는 파일 삭제. 백엔드 미사용 import 11개 정리

### (기록) 점검 기준
- frontend
- apps: customer / instructor 나란히 비교
- 점검 관점: 폴더·파일 명명 일관성, 같은 역할 파일의 위치, 두 앱의 대칭성, 루트 정돈, 이전 구조의 잔재(`alembic/versions__old` 등)
- 결과는 답변으로 받고, 전체를 하나의 **현재 구조 지도**로 합친다.

---

## 5. 다음 작업

1. 실제 환경 검증 — 방법 `docs/operations/verification.md`
   - ✅ (2026-10-02) A: 실제 Supabase 토큰으로 `/auth/me` 200, role CUSTOMER (백엔드 검증 통과)
   - ✅ (2026-10-02) 강사 토큰 + `make apiflow` 14단계 통과(실제 Supabase 토큰·원격 DB, 예약 #4 철회 상태로 남음)
   - ⬜ 앱 실제 로그인(cweb·iweb) / ⬜ 웹 실제 로그인 / ⬜ B: S3
2. 화면 버튼 동작 점검 (`docs/audit/03-runtime-check.md`)
3. ⏸ 보류: 화면 점검 경미 항목 7~11 (`docs/audit/03-runtime-check.md` 경미 표) — 사용자 결정 2026-10-02 "기록해두고 나중에"
4. (포트폴리오 직전) 큰 화면 파일 분리 — `docs/audit/02-frontend-apps.md` §6
2. 관리자 웹 회원 관리 화면 없음(`admin/page.tsx` 는 자리만 있음) — 탈퇴 처리 버튼은 화면이 생길 때
4. **현재 구조 지도** 작성 + 2단계 결정 질문 목록

---

## 6. 결정

### 결정됨
| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-09-25 | 기본 브랜치는 staging 유지 | 작업 → staging → main 흐름에서 PR 기본 대상이 안전한 쪽을 향하게 함 |
| 2026-09-26 | main이 staging보다 앞선 커밋은 역병합하지 않음 | 파일 차이 없이 Release 병합 커밋뿐임 |
| 2026-09-27 | 가독성 = 폴더·파일명·구조 수준. Makefile 명명 등 세부는 보류 | 사용자 우선순위 |
| 2026-09-27 | `docs/audit/`는 커밋하지 않음 | 작업용 임시 자료 |
| 2026-09-27 | `backend/alembic/versions__old/` 유지 | 마이그레이션 리셋 전 이력을 참고용으로 보관 |
| 2026-09-27 | backend 구조 원칙: "도메인 우선, 도메인 내부는 레이어" | 현재 구조가 이미 이 형태(package-by-feature). 공통 영역(`core`, `db`)만 기술 역할로 묶음 |
| 2026-09-27 | `app/security.py` → `app/core/auth/security.py`, users router의 `RegisterCustomerByEmail` → `users/schemas.py` | 최상위 단독 파일과 router 안의 스키마 정의가 위 원칙을 깸. 로직 변경 없음 |
| 2026-09-27 | `app/api/health.py` → `app/core/health.py` | 도메인이 아닌 헬스체크는 공통 인프라(core)에 둠. 레이어 폴더(`api/`) 제거 |
| 2026-09-27 | `domains/auth/`(API) + `core/auth/`(인증 기반) 분담 유지 | 역할 분리가 원칙에 맞음. 로그인 API가 users에 있는 것은 API 경로 영향 때문에 구조 정리 범위 밖 |
| 2026-09-27 | `app/certs/` 일단 유지 | `db/session.py`가 런타임에 읽음. 동작 문제 없음 |
| 2026-09-27 | lesson_note는 독립 도메인 `domains/lesson_notes/`로 분리 | API(`/lesson-notes`)가 이미 독립 |
| 2026-09-27 | 기존 기능은 삭제하지 않음. 목표는 결함 해결과 구조 정리 | 사용자 방침. 중복 코드는 기능을 옮긴 뒤 정리하되 기능 자체는 유지 |
| 2026-09-30 | 고객→강사 매칭을 `domains/matching/` 독립 도메인으로 분리 (실행은 5단계) | 자체 테이블·상태 흐름·요금·채팅방 생성을 가진 별개 기능. instructor는 강사 관리만 담음. API 경로 `/instructors/match`는 유지 |
| 2026-09-30 | posts + content를 하나의 `posts` 도메인으로 병합 (실행은 5단계) | 같은 "게시물"의 중복 구현. 앱이 쓰는 content 쪽 API·테이블을 기준으로 하고, posts에만 있던 대댓글·댓글 수정/삭제·좋아요·피드·검색·공개 동의 등은 전부 살림. 병합만 하고 기능 추가·삭제는 하지 않음 |
| 2026-09-30 | 알림은 `domains/notifications/`로 분리 (병합과 함께) | 게시물 전용이 아닌 공통 기능(예약 알림도 대상) |
| 2026-09-30 | 게시물 참가 매칭(모임 구하기)은 사용자가 원래 넣으려던 기능. 병합된 posts 안의 세부 기능으로 유지하고, 상세 구현은 병합 이후 | 현재는 초안 수준(모집 종류·인원·마감·취소·화면 없음). 병합 때는 옮기기만 함 |
| 2026-09-30 | 게시물 참가 매칭의 권한·예약 결함은 병합 이후 상세 구현 때 수정 | 배포 중단 상태라 노출 위험 낮음. **배포 재개 전 필수 수정** |
| 2026-09-30 | frontend 점검보다 backend 정리를 먼저 마무리 | 사용자 우선순위 |
| 2026-09-30 | backend 도메인 분리·병합을 지금 진행 (1~4단계 "모델 파일 이동 금지" 규칙을 이 작업에 한해 해제) | 테이블 정의가 그대로인 이동은 로컬 임시 DB로 검증 가능. 순서: lesson_notes → matching → notifications → posts+content 병합 → 잔여 정리 |
| 2026-10-01 | 운영 문서는 `docs/operations/`, 요구사항은 `docs/requirements/` (D6) | 폴더명만으로 역할이 보이게. `dev-runbook`이 루트 Makefile·Docker·git까지 다뤄 backend 전용이 아님 |
| 2026-10-01 | `reset_db.py`는 로컬 전용 초기화로 재작성 (D3 일부) | 기존 기능(DB 초기화)은 유지하되 원격 DB 보호. 예전 스크립트는 일회성이고 실행 불가였음 |
| 2026-10-01 | 모델 등록 목록은 `app/db/models.py` 한 곳, passes·chat 제외 유지 | 두 목록이 따로 있으면 init의 create_all 결과가 어긋날 위험. passes·chat 등록은 공유된 마이그레이션 수정 없이는 불가 |
| 2026-10-01 | (D7) booking은 독립 도메인으로 분리하되, 5단계 캘린더 Phase 0–1(휴무 모델 재설계)과 함께 진행 | 예약은 자체 상태 흐름과 `/bookings` 경로가 있어 독립이 맞음. 다만 휴무(HOLIDAY)가 예약 테이블의 한 종류로 저장돼 있어 지금 옮기면 재설계 때 다시 옮겨야 함 |
| 2026-10-01 | (D8) 아이디/비밀번호 로그인을 `domains/auth/`로 옮기고 경로를 `POST /auth/login`으로 변경 (반영 완료) | 인증 API를 auth 한 곳에 모음. 호출처는 웹 `api/dev-login` 1곳이고 배포 중단 중이라 변경 비용이 가장 낮음 |
| 2026-10-01 | (D2) Makefile 타깃 이름은 `<대상><동작>` 소문자 붙여쓰기 (`api` `web` `c` `i` `db` `mig` `dock` `git` `aws` `stg`/`prod`). 예외 `help` `check` `grep` | `iweb`처럼 짧되 이름만으로 대상과 동작이 보이게. 문서(CLAUDE.md §8, README 2종, 운영 문서) 일괄 갱신 |
| 2026-10-01 | (D3) `release` → `gitrelease`로 복원(원래부터 레시피가 잘려 있었음: main에 버전 태그 생성·push 후 복귀). `ddbuild`·`ddrun`(없어진 `Dockerfile.dev` 사용) → `dockdev`(운영 이미지 + 소스 마운트 + reload)로 대체. `verifysetup`(chmod)은 `bash`로 실행하게 바꿔 필요 없어져 제거 | 기능은 유지하고 동작하지 않던 레시피만 고침 |
| 2026-10-01 | (D5) `verify`는 로컬 전용으로 재설계(`make apiverify`): 로컬 DB + 로컬 더미 비밀값으로 서명한 토큰. 실제 Supabase 토큰은 `make apitoken` | 외부 서비스 없이 언제든 같은 결과로 검증. 삭제된 `load_tokens.sh`에 의존하지 않음 |
| 2026-10-01 | 테스트·검증은 로컬 Postgres 컨테이너(`crm-local-db`, 127.0.0.1:55433)와 `backend/scripts/local_env.sh`(더미 값)로 실행. `make apitest`가 매번 빈 DB를 새로 만들어 마이그레이션 → `alembic check` → pytest | 원격 DB(Supabase)에 테스트가 붙지 않게. Codespace가 초기화돼도 명령 하나로 재현 |
| 2026-10-01 | 캘린더 "특정 날짜 시간 휴무"는 `CalendarBlock`(+ `time_slot_id`)으로 기록 | 날짜 단위 조치를 전역 상태(`TimeSlot.is_active`)로 처리하지 않는다는 원칙(CLAUDE.md). 휴무 전체 재설계는 booking 분리와 함께 |
| 2026-10-01 | (D1) 개발 DB는 Supabase(원격) 사용. 테스트·`apiverify`는 로컬 컨테이너 유지 | 사용자 결정. 테스트가 운영 데이터에 붙지 않게 테스트만 로컬로 분리 |
| 2026-10-01 | 개발 중에는 AWS에 배포하지 않고 로컬에서만 개발·테스트 | 사용자 결정. deploy job 실패는 정상, 배포 관련 정리(sync job 등)는 배포 재개 시점으로 미룸 |
| 2026-10-01 | (D4) "반드시 동작할 핵심 흐름"을 따로 정하지 않고 **모든 기능이 에러 없이 동작**하게 만든다. 그 뒤 포트폴리오에 주요 기능·폴더 구조와 그 이유를 작성 | 사용자 결정 |
| 2026-10-01 | 모임 찾기(matching)는 가장 마지막에 구현 | 사용자 결정 |
| 2026-10-01 | 회원 탈퇴 = 개인정보를 지운 탈퇴 상태(WITHDRAWN)로 남김. 결제 기록은 그대로, 다시 로그인 불가(403) | 보존 기간 안의 결제가 있으면 회원을 지울 수 없어서. 사용자가 권장안 선택 |
| 2026-10-01 | 휴무 기능 = 사용자 정의 5가지: ① 모든 강사 캘린더는 매일 07~20시 1시간 슬롯이 기본 ② 정기 휴무일(고객 캘린더에 "정기휴무") ③ 정기 휴무일이 아닌 날 하루 전체를 임시 휴무일로(고객 캘린더에 "임시휴무") ④ 정기 휴무일 중 특정 날짜(전체·일부 시간) 열기 ⑤ 특정 날짜의 특정 시간만 닫기. 슬롯 관리(추가·수정·삭제·전체 ON/OFF)는 유지 | 사용자 정의. ③④⑤는 날짜 단위라 `calendar_blocks`(kind CLOSE/OPEN)에 기록, ①②는 매주 반복 설정(슬롯·정기 휴무 요일) |
| 2026-10-02 | 멤버십·수강권도 계약 기록으로 5년 보존(마지막 변경 시점 기준). 고객·강사 어느 쪽을 지워도 지워지지 않음. 보존 기간 안이면 회원 삭제 409 → 탈퇴 처리. 예약·레슨 노트·채팅은 보존 대상 아님(삭제 시 함께 삭제) | 사용자 결정("회원 탈퇴는 만들고 기록은 남아야 한다"). 전자상거래법 시행령 제6조 "계약 또는 청약철회 등에 관한 기록 5년" |
| 2026-10-01 | 결제 기록은 결제 후 5년 보존 (회원 삭제로 지워지지 않음) | 전자상거래법 시행령 제6조(대금결제 기록 5년), 국세기본법 제85조의3(거래 증빙 5년) |
| 2026-09-27 | `backend/aws/` 삭제 | AWS CLI 설치 번들 잔재. `install_aws_tools.sh`는 매번 새로 내려받아 이 폴더를 쓰지 않고, 실행 파일도 없어 설치기로도 동작하지 않음 |

### 결정 대기
| ID | 결정 | 시점 | 비고 |
|---|---|---|---|

---

## 7. 알려진 결함 (요약)

### 0단계로 당길 것
- `deploy-staging`의 sync job이 최근 병합된 작업 브랜치에 봇 병합 커밋을 push함. 브랜치 삭제 운영과 충돌 → (2026-10-01) 개발 중 배포 안 함 결정으로 배포 재개 시 처리
- ✅ (2026-10-01) 루트 `.gitignore`에 CLAUDE.md §4.2 목록(.env*, *.pem, *.key, id_rsa*, service-account*.json, credentials*.json, secrets.*) 추가, `.env.example` 은 계속 추적. 기존 추적 파일 중 새로 무시되는 것 없음
- (2026-10-01) 테스트·`verify`는 env 없이 로컬 DB로 가능(`make apitest`, `make apiverify`). 실제 Supabase 로그인(`make api`, `apitoken`)만 env 필요. 이전 기록: backend env 없음 → server(실제 로그인), token, flow, verify 불가. (2026-09-30 확인) env 파일 없이도 임시 값과 로컬 Postgres 컨테이너(`postgres:16`, `DB_SSL_DISABLE=1`)로 `alembic upgrade head` 전체 적용과 pytest 35개 통과 → 구조 정리 검증은 로컬 DB로 가능
- ✅ (2026-10-01) devcontainer 에 Node 24 feature 추가(CI와 같은 버전). `safe.directory` 가 예전 경로(`/workspaces/crm-project`)라 적용되지 않던 것도 `${containerWorkspaceFolder}` 로 수정. 다음 Codespace 생성 때 적용됨(지금 환경에서는 재빌드 검증 안 함)

### 4단계(문서 일관성)
- ✅ (2026-09-27 완료) ~~CLAUDE.md §8 명령 이름이 실제와 다름 (`check-db`/`check-schema`/`tokens`/`test` → 실제 `checkdb`/`checkschema`/`token`, test 타깃 없음). 환경 이름은 `production`이 아니라 `prod`~~
- ✅ (2026-10-01) ~~CLAUDE.md §2가 모든 도메인에 repository가 있는 것처럼 기술. 실제로는 posts, notifications만 있음~~ → 전 도메인 전환으로 실제와 일치
- `aws.md`: 실제로는 staging push = staging 배포, **main push = prod 배포**
- ✅ (2026-10-01) ~~README·runbook·troubleshooting의 make 명령 대부분이 옛 이름~~ → 새 이름으로 갱신. 그 밖의 내용(배포 흐름 등)은 아직 4단계 대상
- ✅ (2026-10-02 각 앱 폴더로 이동, instructor .gitignore 수정) ~~`apps/.env.example`이 `apps/`에 있어 Expo가 읽지 않음. instructor는 `.gitignore`가 `.env*`라 example 추적 불가~~
- ✅ (2026-10-01) ~~`SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUD`는 Settings 필드가 아니라 env로 넣어도 반영 안 됨~~ → `Settings.SUPABASE_JWT_ISSUER` 추가(비우면 SUPABASE_URL+/auth/v1), `SUPABASE_JWT_AUD` 는 `SUPABASE_JWT_AUDIENCE` 의 다른 이름으로 받음. deps 는 설정값 직접 사용. 테스트 2개

### 원격 DB(Supabase) 마이그레이션 적용 (2026-10-01, 사용자 승인)
- 적용: `k5l6m7n8o9p0` → `l6m7n8o9p0q1`(병합) → `m7n8o9p0q1r2`(댓글 deleted_at) → `n8o9p0q1r2s3`(calendar_blocks) → `o9p0q1r2s3t4`(예전 게시물 이전) → `p0q1r2s3t4u5`(RLS) → `q1r2s3t4u5v6`(예전 게시물 삭제). 원격 현재 head `q1r2s3t4u5v6`. 이제 이 revision 들은 원격에 공유됐으므로 **수정 금지**(CLAUDE.md §9.2)
- 접속: `backend/.env` 를 Supabase 직접 연결(IPv6 전용) → Session pooler(IPv4)로 사용자가 교체. Codespace 는 IPv6 외부 접속 불가
- 적용 전 원격 확인(읽기 전용, 개수·구조만): 예전 posts 도메인에 실제 데이터(게시물 12·댓글 2·좋아요 4, 알림 9건이 모두 이 게시물을 가리킴), 앱이 쓰던 content 쪽은 0행. `calendar_blocks` 테이블은 원격에 없었음. chat_rooms·chat_messages·alembic_version 은 RLS 꺼짐 + anon 에 읽기·쓰기 권한 → 🔴 anon 키(앱에 공개된 값)로 채팅을 누구나 읽고 쓸 수 있던 상태
- 결정(2026-10-01): 예전 게시물을 새 구조로 옮김(`o9p0q1r2s3t4`). 게시물 ID 유지 → 알림 9건 유효. 고객 없는 FEEDBACK 은 COMMUNITY 로. legacy_* 원본은 백업으로 남김
- 결정(2026-10-01): RLS 가 꺼진 public 테이블 전부 RLS 켬(`p0q1r2s3t4u5`, 정책 없음 = anon·authenticated 차단). 백엔드는 소유자(postgres, RLS 우회)라 영향 없음, 웹이 직접 읽는 users 는 기존 "본인 행" 정책 유지. downgrade 는 보안상 아무것도 안 함
- `n8o9p0q1r2s3` 수정(원격 적용 전): calendar_blocks 가 없으면 모델과 같은 구조로 생성
- 리허설: 원격 public 스키마만(데이터 없음) PostgreSQL 17 로컬 컨테이너에 복제 + 원격과 같은 모양의 가짜 데이터 → 적용·결과 확인·전체 되돌리기·재적용 통과. 빈 DB 경로는 `make apitest` 165개 통과
- 적용 후 원격: version `p0q1r2s3t4u5`, posts 12(공개 10)·post_comments 2·post_likes 4, 알림 9/9 유효, RLS 꺼진 테이블 0, 다른 테이블 행 수 변화 없음, `make dbschema` 통과. 백엔드를 원격 DB로 띄워 공개 피드 10건·댓글 2·좋아요 4 확인
- ✅ (2026-10-01) 모델 선언 ↔ 원격 스키마 차이 해소 — 원격 기준 `alembic check`(`make migcheck`) 통과, 빈 DB 기준(`make apitest`)도 통과
  - ① 모델만 수정(원격이 맞음): FK 삭제 규칙 12개 선언(예약·멤버십·결제·레슨 노트·매칭 → 회원 CASCADE, 예약·결제 → 멤버십 SET NULL, 예약 → 슬롯 CASCADE, 담당 강사 SET NULL), `bookings.topic` NULL 허용(원격에 주제 없는 예약 2건, 빈 DB 에서는 주제 없는 예약이 실패하던 숨은 결함), `instructor_staff` 유니크 이름을 원격과 같게. SQLModel 0.0.16 은 `Field(ondelete=)` 미지원이라 `sa_column=Column(..., ForeignKey(..., ondelete=))`
  - ② 원격에 마이그레이션 `r2s3t4u5v6w7` 적용(승인): 원격에 없던 FK 3개(calendars.host_id, instructor_staff 강사·스태프 → users CASCADE), time_slots 중복 FK 제거, calendar_blocks.calendar_id CASCADE. 행 변화 없음(고아 데이터 0건 확인 후). 리허설: 원격 스키마 복제 + 가짜 데이터로 적용·차이 0·연쇄 삭제·되돌리기 확인
  - ③ 모델 타입을 원격에 맞춤: calendars·time_slots id = BIGINT IDENTITY, time_slots.calendar_id = BIGINT, instructor_staff.id = UUID(gen_random_uuid). 원격 데이터 타입은 그대로. API 응답 형식 변화 없음
  - 원격 현재 head `r2s3t4u5v6w7`
  - ✅ (2026-10-01) 결제 기록 보존: 회원 삭제로 결제가 함께 지워지던 것(CASCADE) → 마이그레이션 `s3t4u5v6w7x8`(원격 적용, payments.customer_id ON DELETE RESTRICT) + `UserRepository.delete` 가 보존 기간 5년(`PAYMENT_RETENTION_YEARS`, 전자상거래법 시행령 제6조 대금결제 기록 5년·국세기본법 제85조의3) 안의 결제가 있으면 409, 기간이 끝난 결제만 있으면 그 기록을 지우고 회원 삭제. 테스트 3개. 원격 head `s3t4u5v6w7x8`
  - 📄 실제 환경 검증 방법(Supabase 로그인·S3)은 `docs/operations/verification.md` (2026-10-01 작성, 실행은 사용자가 나중에)
  - ✅ (2026-10-01) 회원 탈퇴: `POST /users/me/withdraw`(본인), `POST /users/{id}/withdraw`(관리자·담당 강사). 상태 WITHDRAWN·비활성, 이름·이메일·전화·푸시 토큰 등 개인정보 비움, 담당 회원 연결 해제. 결제·예약 기록은 남음. 탈퇴 계정 로그인 403. 보존 중 결제가 있어 삭제가 막히면 409 메시지가 탈퇴 API 를 안내. 마이그레이션 `t4u5v6w7x8y9`(상태 체크에 WITHDRAWN). 남은 것: 앱 탈퇴 화면 없음, Supabase 로그인 계정 자체는 지우지 않음(서비스 키 필요, 로그인해도 백엔드가 403)
  - ✅ (2026-10-01) 휴무 재설계(마이그레이션 `u6v7w8x9y0z1`): 휴무를 가짜 예약(HOLIDAY·WORK_OVERRIDE) 대신 `calendar_blocks.kind`(CLOSE/OPEN)로 기록. 규칙은 `calendar/repository.py` 의 `day_status` 하나를 가용 시간 조회·예약 생성이 함께 씀(정기 휴무일·임시 휴무일·닫은 시간은 API 로 직접 신청해도 400). 가용 응답에 `off_type`(RECURRING/TEMPORARY) 추가(`is_holiday` 유지). 예약은 레슨만(`chk_booking_type`). 규칙: OPEN 은 정기 휴무일에만, 정기 휴무일 전체 CLOSE 불가, 레슨 있는 시간 닫기 409, 레슨 있는 날 열기 해제 409. 강사 승인·강사 계정 생성 시 기본 캘린더(07~20시 13슬롯) 자동 생성. 강사 앱: 휴일전환·영업일전환·이번만 전체영업·시간 활성화·복원을 블록으로, 슬롯 없는 요일엔 "휴일전환" 숨김. 고객 앱: "정기휴무"/"임시휴무" 표시. 테스트 4개 교체·추가(175개)
  - ✅ (2026-10-01, 승인) 원격 적용 `t4u5v6w7x8y9`·`u6v7w8x9y0z1`. 리허설(원격 스키마 복제 + 가짜 데이터: 휴무·영업일 전환 예약 → 블록 변환, 취소된 휴무 삭제, 되돌리기·재적용) 통과 후 적용. 적용 후 원격: 강사 5 중 ACTIVE 4명 모두 캘린더(07~20시 13슬롯, 꺼진 슬롯 0), 예약은 레슨 2건만, 모델 ↔ 원격 차이 0, RLS 꺼진 테이블 0. 원격 head `u6v7w8x9y0z1`
- ✅ (2026-10-02) 계약 기록 보존 + 앱 탈퇴 화면
  - 보존 기간 규칙을 `app/core/retention.py`(5년, `retention_cutoff`) 하나로 모으고 결제·멤버십·수강권이 함께 씀
  - 마이그레이션 `v7w8x9y0z1a2`: memberships·customer_passes 의 고객·강사 FK → RESTRICT, `users.withdrawn_at` 추가(기존 탈퇴 회원은 updated_at 으로 채움). 🔴 발견·수정: customer_passes 의 FK 에 삭제 규칙이 없어(NO ACTION) 수강권이 있는 회원을 삭제하면 DB 오류(500)
  - `UserRepository.delete`: 보존 기간 안의 결제·멤버십·수강권이 있으면 409(무엇 때문인지 표시 + 탈퇴 API 안내). 기간이 지난 기록만 있으면 지우고 삭제(발급 기록이 없는 강사의 수강권 상품도 정리)
  - 탈퇴 시 `withdrawn_at` 기록. 두 앱 프로필에 "회원 탈퇴"(보관 안내 확인창 → 탈퇴 → 로그아웃, 웹·기기 모두)
  - 테스트 6개 추가(181개). 리허설(원격 스키마 복제): FK 4개 RESTRICT, 직접 삭제 차단, 차이 0, 되돌리기·재적용 통과
  - ✅ (2026-10-02, 승인) 원격 적용 `v7w8x9y0z1a2`. 적용 후: 결제·멤버십·수강권 FK 5개 모두 RESTRICT, 모델 ↔ 원격 차이 0, 행 수 변화 없음(회원 16·수강권 1·예약 2), RLS 꺼진 테이블 0. 원격 head `v7w8x9y0z1a2`
  - 재발 방지: 모델을 바꾸면 `make apitest`(빈 DB)와 `make migcheck`(원격) 둘 다 통과해야 한다. 초기 마이그레이션이 현재 모델로 테이블을 만드는 구조라 두 쪽이 따로 어긋날 수 있음
- ✅ (2026-10-01, 사용자 결정 "옮긴 게시물 + 백업 모두 삭제") `q1r2s3t4u5v6_drop_legacy_posts_data` 원격 적용: 옮긴 게시물 12개(댓글 2·좋아요 4는 CASCADE) + 그 게시물 알림 9건 삭제, legacy_* 5개 + `post_consents`(예전 게시물 공개 동의 기록 15행, legacy_posts 에 FK, 코드 미사용) 삭제, 예전 전용 enum(posttype·poststatus·matchstatus) 삭제. 되돌릴 수 없음(downgrade 는 예외). 리허설: 원격 스키마 복제 + 가짜 데이터로 대상만 지워지고 무관한 게시물·댓글·알림은 남는 것 확인. 적용 후 posts·알림 0, 다른 테이블 행 수 변화 없음, RLS 꺼진 테이블 0

### 5단계(코드)
- **서버 직접 호출로 발견 (2026-09-30, 기존 결함, pytest로는 안 잡힘)**
  - ✅ (2026-09-30 해결) `POST /payments`가 항상 422, `GET /openapi.json` 500. 원인: `@limiter.limit` 데코레이터 + `from __future__ import annotations` 조합으로 `data: PaymentCreate`가 쿼리 파라미터로 해석됨. 수정: `payment/router.py`에서 해당 import 제거. 테스트 `tests/test_payment.py` 17개 신설(등록·권한·멤버십 소유·검증·분당 제한·목록·상태 변경)
  - ✅ (2026-09-30 해결) 비밀번호 해시 500(`passlib 1.7.4` + `bcrypt 5.0.0` 비호환). 수정: passlib 제거, `core/auth/security.py`가 bcrypt 직접 호출(함수 이름 유지, 기존 `$2a$`/`$2b$` 해시 호환). 72바이트 초과 비밀번호는 `UserCreate`에서 422. 테스트 `tests/test_password_login.py` 15개 신설
    - 결정: passlib 제거(버전 고정 대신). 이유: passlib는 2020년 이후 관리 중단이라 버전 고정은 문제를 미루는 것
  - ✅ (2026-09-30 해결) 게시물 삭제 후 알림이 남음. 수정: `PostRepository.delete`가 같은 트랜잭션에서 관련 알림 삭제(마이그레이션 없음)
    - 결정: DB FK 대신 repository에서 삭제. 이유: 알림을 예약 등 다른 기능에도 쓸 계획이라 posts 테이블에 묶지 않음
  - ✅ (2026-09-30 결정·반영) 좋아요 취소는 알림 없이 처리하고, 그 좋아요로 생긴 알림도 삭제 → 다시 눌러도 알림이 쌓이지 않음
  - ✅ (2026-10-01 해결) 댓글 삭제 시 "삭제된 댓글입니다" 표시. 마이그레이션 `m7n8o9p0q1r2_add_deleted_at_to_post_comments`(`post_comments.deleted_at` 추가, 데이터 손실 없음, downgrade 시 삭제된 댓글 내용을 같은 문구로 채움). 삭제하면 행은 남기고 원문을 비우며 그 댓글로 생긴 알림도 삭제. 대댓글 유지. 응답 `CommentRead.is_deleted` 추가(웹·두 앱 타입·댓글 표시 갱신). 삭제된 댓글은 수정·재삭제 404, 답글 400, 댓글 수에서 제외
    - 결정: 원문은 지움(작성자가 지운 글, 개인정보), 댓글 수에서 제외
    - 검증: 기존 DB·빈 DB 적용, 데이터 있는 상태 downgrade → 재upgrade, pytest 87개, 서버 직접 호출 13건, 웹 tsc·eslint, 두 앱 tsc(customer는 기존 `cacheDirectory` 1건만)
- **5단계 결함 수정 (2026-10-01)**
  - ✅ 캘린더 "시간 휴무"가 슬롯 전역 비활성화(`TimeSlot.is_active=false`)로 처리돼 모든 날짜에 적용되던 결함 → 날짜별 시간 닫기를 `CalendarBlock`으로 기록
    - 마이그레이션 `n8o9p0q1r2s3`: `calendar_blocks.time_slot_id` 추가(NULL = 하루 전체, FK `ON DELETE CASCADE`). 데이터 손실 없음, downgrade 시 시간 지정 블록 삭제 후 컬럼 제거
    - API: `GET/POST /calendars/me/blocks`, `DELETE /calendars/me/blocks/{id}`. 규칙은 `calendar/repository.py`(`CalendarBlockRepository`): 지난 날짜 400, 남의 슬롯 404, 레슨 예약이 있는 시간 409, 같은 날짜·시간 중복은 그대로 반환
    - 가용 시간 조회는 블록된 날짜·시간 제외(하루 전체 블록은 `is_holiday=true`), 고객 레슨 예약은 블록된 시간에 400
    - 강사 앱 `schedule.tsx`: "시간 휴무"가 블록 생성으로 바뀜, 날짜 패널에 "시간 휴무 · 해제" 표시. 두 앱 `types/api.ts`에 `CalendarBlockRead`
    - 슬롯 전역 ON/OFF(웹 강사 스케줄 화면의 비활성화)는 의도된 전역 설정이라 유지
    - 결정: 기존 휴무(HOLIDAY)·영업일 전환(WORK_OVERRIDE)은 그대로 두고 이 결함만 수정. booking 분리(D7)는 휴무 전체 재설계 때
  - ✅ 캘린더 인덱스 선언 불일치: 모델이 예전 통합 인덱스(`uq_booking_active_slot_date`)를 선언 → DB와 같은 타입별 인덱스 3개로 선언. init 마이그레이션의 `create_all`이 먼저 만들지 않도록 `ddl_if(False)` (빈 DB 스키마 덤프 동일 확인)
  - ✅ passes·chat 모델 변경을 alembic이 감지 못함 → `alembic/env.py`가 비교 명령(check/revision)일 때만 두 모델을 올림. 그 결과 chat 모델이 실제 DB와 다름을 발견(시각 컬럼 시간대 유무, FK `ON DELETE` 누락) → 규칙(9.3)대로 모델 선언을 DB에 맞춤(동작 변화 없음). 이제 `alembic check`가 전체 모델 기준으로 통과
  - ✅ 같은 이메일의 다른 Supabase 계정 로그인 시 500 → 409 "이미 다른 계정에 등록된 이메일"
  - ✅ S3 삭제 재시도 없음 → botocore 재시도(최대 5회, 지수 백오프), 네트워크 오류도 잡아 키와 함께 기록. 재시도 후에도 실패하면 객체는 남음(로그로 수동 정리)
  - ✅ `alembic/env.py`의 DB 주소 출력 제거
  - ✅ `verify.sh` 재작성(D5 결정): 로컬 DB·로컬 더미 서명 토큰으로 외부 서비스 없이 실행, 서버를 프로세스 그룹째 종료(uvicorn 잔류 해결)
  - ✅ customer 앱 tsc 오류(`FileSystem.cacheDirectory`) → `expo-file-system/legacy` import. 웹·두 앱 tsc 모두 통과
  - ✅ CI: backend에 `alembic check` 단계 추가, `apps-CI.yml`(두 앱 tsc) 신설·orchestrator 연결. (정정) frontend CI는 lint만이 아니라 build(타입 검사 포함)까지 이미 함
  - ✅ 테스트를 쓰며 발견·수정: 레슨 노트를 다른 강사의 예약에도 작성 가능(RBAC 누락) → 403 / 채팅 메시지 전송 시 방의 `last_message_at`이 항상 NULL(서버 기본값 받기 전에 대입) / 채팅 `before` 커서가 UUID가 아니면 500 → 400 / 2000자 초과 메시지 500 → 422 / 수강권 상태·횟수·가격 입력 검증 없음 → 422
  - 테스트: 88 → 141개. 신설 `test_calendar.py` 9, `test_auth.py` 19, `test_passes.py` 16, `test_lesson_notes.py` 4, `test_chat.py` 5
- ✅ (2026-10-01 휴무 재설계로 해소) ~~휴무가 예약 테이블의 가짜 예약(HOLIDAY)으로 저장됨. 슬롯 없는 요일은 이미 휴무라 실사용 문제는 작지만, 강사 앱이 그런 날에도 "휴일전환" 버튼을 보여 주고 누르면 400(아무 슬롯이나 골라 보내 요일 불일치). 슬롯을 지우면 그 슬롯에 걸린 휴무도 CASCADE 로 사라짐. 휴무 표현이 5가지(슬롯 요일·정기 휴무 요일·HOLIDAY·WORK_OVERRIDE·CalendarBlock)로 흩어짐 → 휴무 개념 정리 필요~~
- init 마이그레이션(`91d68413f8d6`)이 `create_all`로 **현재 모델 코드**를 읽어 테이블 생성 → 모델을 바꾸면 빈 DB 구축 결과가 달라질 수 있음. 모델 변경 시 `make apitest`(빈 DB 새로 구축 + alembic check)로 확인
- ✅ (2026-09-30 해소) 게시물 체계 이중화, 게시물 참가 매칭 초안의 권한·예약 결함 2건, `MatchRequest` 이름 중복 → posts+content 병합으로 제거. 모임 찾기는 matching 도메인에서 새로 설계 예정(모집 인원·마감·신청·취소·모임 채팅, customer 앱에 "모임채팅" 탭만 있음)
- ✅ repository 전환 (2026-10-01): 12개 도메인 전부 `repository.py` 보유. router는 요청 파싱·권한 확인·응답 변환만 하고 DB를 직접 다루지 않음(`session.execute/select` 0건)
  - 순서: payment → membership → passes → calendar(`CalendarRepository`·`BookingRepository`·`CalendarBlockRepository`) → lesson_notes → chat → matching → auth → instructor → users
  - 도메인 사이 호출은 repository 끼리 (예: 예약 완료 → `PassRepository.deduct_for_lesson`·`MembershipRepository.deduct_for_lesson`, 매칭 수락 → `ChatRepository.ensure_room_for_match`). 같은 세션이라 한 트랜잭션
  - calendar `router.py` 1,230 → 383줄. booking 은 클래스로만 나눠 둠 → D7(휴무 재설계) 때 `domains/booking/`으로 옮기기 쉬움
  - 옮기기 전에 현재 동작을 고정하는 테스트 먼저 추가: `test_booking_flow.py` 13(상태 전환 9종·휴무·영업일 전환·멤버십·권한), `test_instructor.py` 5, `test_users_api.py` 5. 테스트 141 → 165개
  - 전환 중 발견·수정: 🔴 `.ics` 다운로드에 권한 확인 없음(누구나 남의 예약 정보 다운로드) → 예약 고객·강사·관리자만 / 🔴 강사의 고객별 통계가 예약이 있으면 항상 500(집계 열 이름 오류) / 수강권 사용 횟수가 총 횟수를 넘을 수 있음 → 400
  - 응답 변화: 예약 취소·철회 응답(`BookingCancelResponse`)의 `cancel_reason`이 이제 실제 값으로 채워짐(예전엔 필드만 있고 항상 null). 강사 재신청 응답에 `id` 포함
- ⬜ `make gitrelease`·`gitrollback`·`gitbranch`는 push 하는 대화형 명령이라 문법 검사만 함(실행 검증 안 함)

---

## 8. 운영 상태

- AWS 백엔드 배포 중단 (CLAUDE.md 7.3). deploy job 실패는 정상
- 기본 브랜치: staging. 작업 브랜치 → staging → Release PR → main
- CLAUDE.md 개정본은 `crm` 브랜치(`76fdfb4`)에만 있고 staging 미반영
- Codespace는 언제든 삭제될 수 있다고 가정한다. 남아야 할 것은 커밋·푸시하고, 비밀값은 Codespaces Secrets에 둔다
