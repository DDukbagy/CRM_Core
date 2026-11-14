# HS256 폴백 평소 끄기

- 상태: 완료
- 기간: 2026-11-13 ~ 2026-11-14
- 브랜치 / PR: `crm`
- 관련 작업:

## 1. 문제

백엔드는 API 요청마다 토큰을 검증한다. 먼저 Supabase 토큰으로 검증하고, 실패하면 **항상** 백엔드가 직접 서명한 로컬 HS256 토큰으로 다시 검증한다 (`backend/app/core/auth/deps.py` `verify_any_access_token`). 로컬 토큰은 아이디/비밀번호 로그인(`POST /auth/login`)이 발급한다.

- 설계상 이 폴백은 Supabase 장애 때만 여는 비상구인데, 켜고 끄는 설정이 없어 평소에도 두 번째 인증 경로가 열려 있다. 로컬 토큰 서명 키(`SECRET_KEY`)가 새면 Supabase 를 거치지 않고 아무 사용자의 토큰이나 만들 수 있다.
- 로그인(`POST /auth/login`)도 평소에 늘 열려 있다. 토큰을 쓰지 못하더라도, 200 이 오면 그 비밀번호가 맞다는 것을 알 수 있어 비밀번호를 맞혀 보는 창구가 된다 (분당 5회 제한은 있음).
- 웹·두 앱·스크립트는 모두 Supabase 로그인·토큰만 쓴다. 평소에 이 경로를 쓰는 곳은 없다.
- 폴백이 쓰여도 경고가 남지 않는다. 대신 키 길이를 info 로그로 남기고, 실패하면 스택 전체를 남긴다. Supabase 검증이 왜 실패했는지(형식·키 불일치·JWKS 조회 실패)는 남지 않는다.

## 2. 테스트 명세

- [ ] 비상구 설정을 따로 주지 않으면(기본값 꺼짐) → 로컬 HS256 토큰으로 API 를 요청해도 `401 Invalid token` 이다 (다른 잘못된 토큰과 같은 응답)
- [ ] Supabase 토큰 검증이 실패하고 비상구 설정이 켜져 있으면 → 올바른 로컬 HS256 토큰은 통과한다
- [ ] 비상구 설정이 켜져 있어도 → 잘못된 로컬 토큰(다른 키로 서명 등)은 `401 Invalid token` 이다
- [ ] 비상구가 쓰이면(설정 켜짐 + 로컬 토큰 통과) → WARNING 로그가 남고, Supabase 검증이 실패한 원인이 들어간다 (토큰 내용·키 정보는 남기지 않는다)
- [ ] 비상구 설정과 관계없이 → 올바른 Supabase 토큰은 통과한다
- [ ] 비상구 설정이 꺼져있는데 누군가 login을 호출하면 → /auth/login은 404
- [ ] 비상구 설정이 켜졌을때(supabase로그인에 장애가 생겼을때) → `POST /auth/login` 은 아이디·비밀번호가 맞으면 토큰을 발급한다

## 3. 재현 (고치기 전)

- 테스트 이름 또는 실행한 명령:
  - 검증: `make apitest ARGS="tests/test_auth.py -k 'fallback or local_token' --tb=short --show-capture=no -rA -p no:cacheprovider"` (`backend/tests/test_auth.py` 4개, 명세 1~4 에 하나씩)
  - 로그인: `make apitest ARGS="tests/test_password_login.py -k fallback_off --tb=short --show-capture=no -rA -p no:cacheprovider"` (`backend/tests/test_password_login.py` `test_login_is_404_when_fallback_off`, 명세 6. 맞는 비밀번호·틀린 비밀번호 두 경우)
  - 명세 5 는 기존 `test_first_login_creates_customer_once` 등 Supabase 토큰 테스트, 명세 7 은 기존 `test_login_issues_token`(설정을 켠 상태로 바꿈)이 확인
- 실행 환경: 로컬 Postgres 컨테이너 (`make apitest` 가 `crm_test` DB 를 새로 만들고 마이그레이션 적용)
- 커밋: `f67a2db` (수정 전 `deps.py`) + 테스트 파일. 테스트가 설정을 켤 수 있도록 설정 항목(`LOCAL_JWT_FALLBACK_ENABLED`)만 먼저 추가한 상태
- 결과: 명세 1·4·6 이 실패했다. 명세 2·3 은 지금도 맞는 동작이라 통과한다 (고친 뒤에도 깨지지 않아야 하는 동작).

검증 (`test_auth.py`):

```text
F..F                                                                     [100%]
=================================== FAILURES ===================================
_________________ test_local_token_rejected_when_fallback_off __________________
tests/test_auth.py:188: in test_local_token_rejected_when_fallback_off
    assert r.status_code == 401, r.text
E   AssertionError: {"id":"8a29f1f0-...","username":"auth-8a29f1f0","display_name":"auth-test","role":"CONTENT_MANAGER"}
E   assert 200 == 401
E    +  where 200 = <Response [200 OK]>.status_code
__________________ test_fallback_use_logs_warning_with_reason __________________
tests/test_auth.py:230: in test_fallback_use_logs_warning_with_reason
    assert len(warnings) >= 1
E   assert 0 >= 1
E    +  where 0 = len([])
=========================== short test summary info ============================
PASSED tests/test_auth.py::test_local_token_accepted_when_fallback_on
PASSED tests/test_auth.py::test_wrong_key_local_token_rejected_when_fallback_on
FAILED tests/test_auth.py::test_local_token_rejected_when_fallback_off - Asse...
FAILED tests/test_auth.py::test_fallback_use_logs_warning_with_reason - asser...
2 failed, 2 passed, 21 deselected, 1 warning in 0.26s
```

로그인 (`test_password_login.py`, 토큰 문자열은 줄임):

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
_____________ test_login_is_404_when_fallback_off[right-password] ______________
tests/test_password_login.py:188: in test_login_is_404_when_fallback_off
    assert res.status_code == 404, res.text
E   AssertionError: {"access_token":"eyJhbGciOiJIUzI1NiIs...","token_type":"bearer","role":"CONTENT_MANAGER","display_name":"pw-a3a8b24e"}
E   assert 200 == 404
E    +  where 200 = <Response [200 OK]>.status_code
_____________ test_login_is_404_when_fallback_off[wrong-password] ______________
tests/test_password_login.py:188: in test_login_is_404_when_fallback_off
    assert res.status_code == 404, res.text
E   AssertionError: {"error":{"code":"HTTP_EXCEPTION","message":"아이디 또는 비밀번호가 틀렸습니다.","request_id":"..."}}
E   assert 400 == 404
E    +  where 400 = <Response [400 Bad Request]>.status_code
=========================== short test summary info ============================
FAILED tests/test_password_login.py::test_login_is_404_when_fallback_off[right-password]
FAILED tests/test_password_login.py::test_login_is_404_when_fallback_off[wrong-password]
2 failed, 16 deselected, 1 warning in 1.04s
```

| 명세 | 기대 | 실제 (고치기 전) | 뜻 |
|---|---|---|---|
| 1. 설정 꺼짐 + 로컬 토큰 | 401 | 200, 사용자 정보 반환 | 설정과 관계없이 비상구가 늘 열려 있음 |
| 2. 설정 켜짐 + 로컬 토큰 | 200 | 200 | 통과 (유지해야 할 동작) |
| 3. 설정 켜짐 + 다른 키 로컬 토큰 | 401 | 401 | 통과 (유지해야 할 동작) |
| 4. 비상구 사용 시 WARNING 로그 | 1개 이상, `reason=` 포함 | 0개 | 비상구가 쓰여도 경고가 없음 (info 로그에 키 길이만) |
| 6. 설정 꺼짐 + `/auth/login` (맞는 비밀번호) | 404 | 200, 토큰 발급 | 평소에도 로컬 토큰을 발급함 |
| 6. 설정 꺼짐 + `/auth/login` (틀린 비밀번호) | 404 | 400 | 비밀번호가 맞는지 틀린지 응답으로 드러남 |

## 4. 원인

`verify_any_access_token` 이 Supabase 검증 실패(`SupabaseJWTError`)를 받으면 조건 없이 `_verify_local_hs256_token` 을 부른다. 켜고 끄는 설정이 없다.

- `backend/app/core/auth/deps.py` `verify_any_access_token`: `except SupabaseJWTError: return _verify_local_hs256_token(token)`. 비상구가 열리는 조건이 "Supabase 검증 실패" 하나뿐이다 (명세 1).
- 백엔드는 Supabase 검증이 실패한 이유가 장애인지, 위조·잘못된 토큰인지 구분할 수 없다. 그래서 "실패하면 자동으로 연다"는 사실상 "늘 열려 있다"와 같다. 비상구는 사람이 장애를 확인하고 여는 설정이어야 한다.
- 같은 파일 `_verify_local_hs256_token`: 검증 전에 `alg`·`key_len` 을 info 로 남기고, 성공도 info, 실패는 `logger.exception` 으로 스택 전체를 남긴다. Supabase 검증 실패 원인은 `except` 에서 버려져 어디에도 남지 않는다 (명세 4).
- `backend/app/domains/auth/repository.py` `AuthRepository.login`: 설정을 보지 않고 바로 아이디·비밀번호를 확인해 토큰을 발급한다 (명세 6). 비상구의 발급 쪽도 늘 열려 있다.
- `supabase_jwt.py` 는 실패 원인을 `SupabaseJWTError("Invalid token") from e` 처럼 `__cause__` 에 담아 올린다. 원인 정보는 이미 있었고, 꺼내 쓰지 않았을 뿐이다.

## 5. 선택지와 결정

| 선택지 | 방식 | 장점 | 단점 |
|---|---|---|---|
| A. 검증만 설정으로 켜고 끔 | `LOCAL_JWT_FALLBACK_ENABLED`(기본 꺼짐)가 꺼져 있으면 Supabase 실패 시 바로 401. 로그인(`/auth/login`)은 늘 열어 둔다 | 바꿀 곳이 `deps.py` 한 곳. 실제로 문을 여는 건 검증이라, 검증만 닫으면 평소 경로가 하나로 줄어든다. 장애 때 설정만 켜면 바로 쓸 수 있다 | 설정이 꺼져 있을 때 로그인하면 200 과 토큰을 받지만 그 토큰은 어디서도 쓸 수 없어 헷갈릴 수 있다 |
| B. 발급·검증을 함께 켜고 끔 | 같은 설정으로 `/auth/login` 도 막는다 (꺼져 있으면 비밀번호 확인 전에 거부) | 평소에 비밀번호를 맞혀 볼 수 있는 창구가 사라진다 (토큰은 못 써도 200 이면 비밀번호가 맞다는 것을 알 수 있음). 쓸 수 없는 토큰을 발급하지 않아 일관된다 | `auth/repository.py`·로그인 테스트 5개까지 바뀐다. 닫혀 있을 때 응답 코드를 따로 정해야 한다 |
| C. 폴백을 아예 제거 | 로컬 토큰 검증·발급 코드를 지운다 | 인증 경로가 하나뿐이라 가장 단순하다 | Supabase 장애 때 쓸 수단이 없어진다. 설계 의도(긴급 대응 수단, CLAUDE.md 10.3)와 다르다 |
| D. 그대로 두고 로그만 보강 | 동작은 두고 경고 로그만 추가 | 동작 변경이 없다 | 평소에도 두 번째 경로가 열려 있다는 문제가 그대로 남는다 |

꺼져 있을 때 로컬 토큰에 줄 응답도 함께 정한다: 다른 잘못된 토큰과 같은 일반 `401 Invalid token` (비상구 존재를 밖에 드러내지 않음, 원인은 서버 로그에만) / 구분된 메시지 (예: "Local token fallback disabled", 디버깅은 쉽지만 내부 설정이 드러남).

- 고른 것: B. 로그인과 HS256 검증을 함께 비상구로(평소에는 둘 다 닫힘)
- 이유: 로그인의 기본값은 supabase로 두는데 백엔드 /auth/login을 열어둘 필요가 없음 혹시나 열어두었다가 발생하는 보안 트러블을 미연에 방지

## 6. 수정

- 바꾼 파일:
  - `backend/app/core/config.py`: 설정 `LOCAL_JWT_FALLBACK_ENABLED: bool = False` 추가 (기존 설정 이름은 그대로)
  - `backend/app/core/auth/deps.py` `verify_any_access_token`: Supabase 검증이 실패하면 설정을 확인한다. 꺼져 있으면 바로 `401 Invalid token`. 켜져 있을 때만 로컬 HS256 검증을 하고, 통과하면 `WARNING local jwt fallback used: sub=... reason=<원인>` 을 남긴다. 원인은 새 함수 `_supabase_failure_reason` 이 `SupabaseJWTError.__cause__` 에서 예외 이름과 메시지만 꺼낸다 (토큰 내용은 넣지 않음)
  - 같은 파일 `_verify_local_hs256_token`: `key_len` info 로그·성공 info 로그 제거. 실패는 스택 없이 `WARNING local jwt fallback: rejected (<예외 이름>)` 한 줄
  - `backend/app/domains/auth/repository.py` `AuthRepository.login`: 설정이 꺼져 있으면 아이디·비밀번호를 확인하기 **전에** 404. 확인 뒤에 막으면 맞을 때와 틀릴 때의 응답 시간(비밀번호 해시 확인) 차이로 비밀번호가 맞는지 짐작할 수 있어서다. 404 는 없는 주소와 같은 본문(`{"detail":"Not Found"}`)이 되도록 Starlette 예외로 보낸다 (FastAPI `HTTPException` 은 앱 오류 처리기가 `{"error": ...}` 로 바꿔 없는 주소와 달라진다)
  - `backend/tests/test_password_login.py`: 로그인 테스트는 설정을 켠 상태로 돌리는 fixture(`_fallback_on`, 자동 적용) 추가. 명세 6 테스트 `test_login_is_404_when_fallback_off` 추가
  - `backend/tests/test_auth.py`: 명세 1~4 테스트 4개. 기존 `test_local_fallback_token_is_accepted` 는 설정을 켜는 명세 2 테스트로 바뀜 (설정 없이 통과하면 안 되므로)
  - `docs/operations/env-setup.md`: 새 변수 이름과 용도 한 줄 (켜면 로그인과 검증이 함께 열림)
- 영향 범위 (API 계약, DB, 웹·앱):
  - API 계약: 요청·응답 형태는 그대로. 설정이 꺼진 기본 상태에서 로컬 토큰 요청 200 → 401, `POST /auth/login` 200·400 → 404. 둘 다 쓰는 클라이언트가 없다
  - DB: 스키마·마이그레이션 변경 없음
  - 웹·두 앱·스크립트(`apitoken`·`smoke`·`apiverify`): Supabase 로그인·토큰만 쓰고 `/auth/login` 을 부르지 않으므로 영향 없음
  - 배포 설정(데모 Render·copilot): 바꾸지 않음. 기본값이 꺼짐이라 평소 원하는 동작 그대로
- 커밋 / PR: `crm` 브랜치 한 커밋 (재현 테스트·수정·문서)

## 7. 결과 (고친 후)

- 같은 테스트의 실행 결과:

```text
=========================== short test summary info ============================
PASSED tests/test_auth.py::test_local_token_rejected_when_fallback_off
PASSED tests/test_auth.py::test_local_token_accepted_when_fallback_on
PASSED tests/test_auth.py::test_wrong_key_local_token_rejected_when_fallback_on
PASSED tests/test_auth.py::test_fallback_use_logs_warning_with_reason
4 passed, 21 deselected, 1 warning in 0.19s
```

```text
=========================== short test summary info ============================
PASSED tests/test_password_login.py::test_login_is_404_when_fallback_off[right-password]
PASSED tests/test_password_login.py::test_login_is_404_when_fallback_off[wrong-password]
2 passed, 16 deselected, 1 warning in 0.51s
```

- 설정이 꺼져 있을 때 `/auth/login` 과 없는 주소의 응답이 같다:

```text
POST /auth/nope   404 {"detail":"Not Found"}
POST /auth/login  404 {"detail":"Not Found"}
```

- 비상구가 쓰일 때 실제로 남는 로그 (로컬 토큰은 Supabase 키와 다른 키로 서명돼 있어 "서명 불일치"가 원인으로 잡힘):

```text
WARNING  auth:deps.py:174 local jwt fallback used: sub=b85eabf4-... reason=JWTError: Signature verification failed.
```

- 백엔드 전체: `make apitest` 212 passed (명세 5·7 을 확인하는 기존 auth·로그인 테스트 포함)

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
| 명세 1~4 테스트 | 2 failed, 2 passed | 4 passed | 로컬 Postgres 컨테이너, `make apitest` |
| 명세 6 테스트 (2가지 경우) | 2 failed | 2 passed | 같음 |
| 설정 꺼짐 + `/auth/login` | 200 (맞음) / 400 (틀림) | 404 / 404 | 같음 |
| 설정 꺼짐 + 로컬 토큰 | 200 (통과) | 401 | 같음 |
| 비상구 사용 시 WARNING 로그 | 0개 | 1개 (`reason=` 포함, 토큰·키 정보 없음) | 같음 |

## 8. 남은 것

- 경고 알림: 비상구가 쓰이면 담당자에게 알려야 하지만 백엔드에 메일 발송 기능이 없다. Sentry 가 연결돼 있으므로(`app/main.py`) WARNING 로그를 Sentry 이벤트로 보내고 알림 규칙으로 메일을 받는 방식을 배포 재개 때 검토
- 비상구의 실제 쓸모: Supabase 로 가입한 사용자는 우리 DB 에 비밀번호가 없을 수 있어(`users.password` nullable), 장애 때 비상구를 켜도 `/auth/login` 으로 토큰을 받을 수 없다. 장애 대응 절차(누가, 어떻게 로컬 토큰을 받는지)는 별도로 정해야 한다
- 비상 로그인 경로가 화면에 없다: 웹(`frontend/src/app/login/actions.ts`)과 두 앱은 Supabase 로만 로그인하고 `/auth/login` 을 부르지 않는다. 그래서 비상구를 켜도 일반 사용자는 쓸 수 없고, 지금은 운영자가 직접 API 를 부르는 용도에 가깝다. 또 백엔드는 Supabase 공개키(JWKS)를 10분 캐시하므로(`supabase_jwt.py` `_fetch_jwks`) 장애 초기에는 이미 로그인한 사용자의 토큰은 계속 검증되고, 막히는 것은 주로 새 로그인·토큰 갱신이다. 비상구를 쓸모 있게 만들지(화면의 비상 로그인 경로·관리자 비밀번호·대응 절차) 제거할지는 정식 출시 전에 운영 방식과 함께 정한다
- 횟수 제한(분당 5회)은 우리 코드보다 먼저 실행돼, 설정이 꺼져 있어도 6번째 요청부터 `/auth/login` 은 429 다. 없는 주소는 429 가 나지 않으므로 끈질기게 보면 "이 주소에 무언가 있다"는 것은 알 수 있다. 비밀번호 확인·토큰 발급은 되지 않아 위험은 없고, 막으려면 횟수 제한 구조를 바꿔야 해 이번 범위에서 뺐다
- 설정을 켜고 끄는 절차(누가 켜고 언제 끄는지)를 운영 문서에 적는 것은 정식 배포 재개 때

## 9. 배운 것

처음에는 로그인할 때 Supabase 검증 → HS256 검증 순서로 진행되고, HS256 이 최종 방어선이라고 생각했다. 그래서 로그인은 열어 둬도 된다고 봤다.
실제로는 로그인(토큰 받기)과 검증(API 요청마다)이 따로 일어나고, HS256 폴백은 방어선이 아니라 검증에 실패한 토큰에 한 번 더 통과할 기회를 주는 문이었다. 또 대칭키는 검증할 수 있는 쪽이 위조도 할 수 있어서, 키가 새면 그 키로 만든 토큰이 그대로 통과한다.
로그인도 토큰은 못 쓰더라도 200 이 오면 비밀번호가 맞다는 것이 드러나므로, 최종적으로 백엔드 로그인(`/auth/login`)과 HS256 검증을 함께 필요할 때만 켜지게 했다.
다만 지금은 비상구를 켜도 들어올 화면이 없어 쓸모가 애매하다. 실제 장애 때의 대응 절차와 경로를 정식 출시 전에 고민해야 한다.
