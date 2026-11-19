# 로깅 체계 (JSON 로그 · 요청 ID · 사용 로그)

- 상태: 완료
- 기간: 2026-11-18
- 브랜치 / PR: `crm`
- 관련 작업: [HS256 폴백 평소 끄기](hs256-fallback-off.md), [변이 테스트](test-mutation-check.md)

## 1. 문제

백엔드 로그는 `logging.basicConfig` 의 텍스트 한 줄(`시각 레벨 이름 메시지`)이고, 요청 로그는 `app/core/middleware.py` 가 `key=value` 텍스트로 남긴다. 요청 ID 와 처리 시간은 이미 있지만 다음이 문제다.

- **형식**: 텍스트라 CloudWatch·Render 로그에서 필드(상태 코드, 처리 시간, 요청 ID)로 거르거나 집계하기 어렵다. 다음 작업인 부하 테스트에서 느린 요청을 찾는 데도 필드 검색이 필요하다.
- **사용 로그 없음**: `app/domains/*` 에 로그가 하나도 없다. 예약 확정·완료·차감·결제 등록이 언제 누구에 의해 일어났는지 로그로 알 수 없다.
- **인증 실패 원인 없음**: 비상구 설정(`LOCAL_JWT_FALLBACK_ENABLED`)이 꺼져 있으면 Supabase 검증 실패가 원인 없이 `401` 이 된다. 2026-11-17 데모 장애 때 원인 찾기가 어려웠던 이유 중 하나다.

미들웨어와 예외 처리기만 붙인 작은 앱으로 확인한 결과 (403 을 내는 경로, 예외를 던지는 경로):

```text
INFO app.request request_id=7c9e... method=GET path=/denied status=403 duration_ms=0.50 client=testclient
==> /denied 403 True
ERROR app.request request_id=776d... method=GET path=/boom status=500 duration_ms=0.23 client=testclient
ERROR uvicorn.error Unhandled exception request_id=776d... method=GET path=/boom path_params={} user_id=None
ERROR app.core.exceptions Unhandled exception request_id=776d... method=GET path=/boom path_params={} user_id=None
==> /boom 500 False
```

(`==>` 줄: 경로, 상태 코드, 응답에 `X-Request-ID` 헤더가 있는지)

- **500 하나에 스택 트레이스 3번**: 미들웨어 `logger.exception`, 예외 처리기의 `uvicorn.error`, 예외 처리기의 `app.core.exceptions`
- **500 응답에 `X-Request-ID` 헤더 없음**: 본문에는 `request_id` 가 있지만 헤더는 정상 응답일 때만 붙는다
- **미들웨어의 `HTTPException` 분기는 실행되지 않는다**: 403 이 그 분기를 거치지 않고 INFO 로 남았다. 주석의 "401/403 은 warning" 은 실제로 일어나지 않는다
- **받은 `X-Request-ID` 를 검사 없이 사용**: 길이 제한이 없고, 줄바꿈이 섞인 값으로 로그 줄을 위조할 여지가 있다

## 2. 테스트 명세

- [ ] 1. 정상 요청을 보내면 → 응답 헤더에 `X-Request-ID` 가 있고, 요청 로그 한 줄에 요청 ID·메서드·경로·상태·응답 시간이 있다
- [ ] 2. 서버에서 처리 못 한 오류(500)가 나면 → 응답 헤더에 `X-Request-ID` 가 있고, 스택 트레이스는 1번만 남는다
- [ ] 3. 클라이언트가 보낸 `X-Request-ID` 가 너무 길거나 줄바꿈이 섞여 있으면 → 그 값을 버리고 새로 만든다
- [ ] 4. Supabase 토큰 검증에 실패하면 → 응답은 401 이고, 로그에 실패 원인이 남는다. 단, 로그에 토큰은 남지 않는다
- [ ] 5. 예약 완료가 성공하면 → 사용 로그에 예약 번호, 처리한 사람 ID, 차감된 수강권 번호가 남는다
- [ ] 6. 예약 완료가 거부(409)되면 → 사용 로그가 남는다
- [ ] 7. `LOG_FORMAT=json` 이면 → 로그 한 줄이 JSON 으로 읽히고, `LOG_FORMAT=text` 이면 텍스트 형식으로 나온다

## 3. 재현 (고치기 전)

- 테스트 이름 또는 실행한 명령: `make apitest ARGS="tests/test_logging.py -p no:randomly --tb=line"` (명세 1~7, 9개)
- 실행 환경: 로컬 Postgres 컨테이너 (`make apitest`)
- 커밋: `56188e6` + 테스트 파일 `backend/tests/test_logging.py`

9개 모두 명세가 가리키는 이유로 실패한다. (3번의 500자 값은 줄여 적음)

```text
E   AttributeError: 'LogRecord' object has no attribute 'request_id'                                  ← 명세 1: 로그에 칸이 없음
E   AssertionError: assert 'X-Request-ID' in Headers({'content-length': '131', 'content-type': 'application/json'})  ← 명세 2: 500 응답에 헤더 없음
E   AssertionError: assert 'aaaa...aaaa' != 'aaaa...aaaa'                                             ← 명세 3: 긴 값이 그대로 돌아옴
E   AssertionError: assert 'abc\nFAKE log line' != 'abc\nFAKE log line'                              ← 명세 3: 줄바꿈 값이 그대로 돌아옴
E   assert False                                                                                      ← 명세 4: 실패 원인(reason=) 로그 없음
E   assert 0 == 1                                                                                     ← 명세 5: 완료 사용 로그 없음
E   AssertionError: assert 'booking.complete_rejected' in []                                          ← 명세 6: 거부 사용 로그 없음
E   ModuleNotFoundError: No module named 'app.core.logging'                                           ← 명세 7: 형식 설정 없음 (json·text 2개)
9 failed, 1 warning in 0.49s
```

## 4. 원인

- **스택 3번**: Starlette `BaseHTTPMiddleware` 는 안쪽에서 처리되지 않은 예외를 `call_next` 에서 다시 던진다. 미들웨어가 이를 잡아 `logger.exception` 으로 남기고 다시 던지면, 가장 바깥의 `ServerErrorMiddleware` 가 `Exception` 처리기(`exceptions.py`)를 부르고, 처리기가 같은 내용을 두 로거에 또 남긴다. 게다가 `ServerErrorMiddleware` 는 응답을 보낸 뒤 예외를 다시 던지므로("서버가 기록할 수 있게"), 실제 uvicorn 에서는 `Exception in ASGI application` 으로 네 번째 스택이 남는다 (테스트 클라이언트는 이 마지막 단계를 거치지 않아 3번으로 보였다).
- **500 헤더 없음**: 500 응답은 미들웨어 바깥(`ServerErrorMiddleware`)에서 만들어지므로, 미들웨어의 "응답 헤더 붙이기" 코드에 도달하지 않는다.
- **`HTTPException` 분기**: `HTTPException` 은 미들웨어보다 안쪽의 `ExceptionMiddleware` 가 이미 응답으로 바꾼다. 미들웨어에는 예외가 아니라 403 응답이 돌아온다.
- **인증 실패 원인**: `auth/deps.py` `verify_any_access_token` 에서 비상구가 꺼져 있으면 `SupabaseJWTError` 를 기록 없이 401 로 바꾼다 (#84 에서 원인 기록은 비상구를 썼을 때만 넣었다).

## 5. 선택지와 결정

| 선택지 | 장점 | 단점 |
|---|---|---|
| A. 장애 로그만: JSON 형식 + 1절 결함 + 인증 실패 원인 | 변경 범위가 `app/core` 에 머문다 | 계획의 "사용 로그"가 빠진다. 누가 언제 차감했는지 여전히 모른다 |
| B. A + 사용 로그 (예약 생성·확정·완료·노쇼·취소, 수강권 차감·발급·횟수 추가·수정, 결제 등록·상태 변경) | 장애 로그와 사용 로그를 나눠 볼 수 있다. 부하 테스트·운영 추적에 쓴다 | 거래성 도메인 repository 에 한 줄씩 들어간다. commit 이후에 남겨야 실패한 처리가 기록되지 않는다 |

| 함께 정한 것 | 선택지 |
|---|---|
| 클라이언트 IP | 남김 / 뺌 / 일부 가림 |
| 로컬 출력 | `LOG_FORMAT=text\|json` 설정 추가(기본 json) / 항상 json |

- 고른 것: B, IP 남김 + LOG_FORMAT
- 이유: 데모 장애 때 로그에 401·500만 있고 원인이 없어 추적이 어려웠다. 운영 중 문제가 생겼을 때 추측이 아니라 기록으로 확인할 수 있어야 한다고 판단했다.

## 6. 수정

- 바꾼 파일:
  - `app/core/logging.py` (새 파일): `JsonFormatter`·`TextFormatter`·`build_formatter`, `configure_logging`(루트 핸들러 하나, uvicorn 로그도 같은 형식으로 모으고 uvicorn 접근 로그는 끔 — 요청 로그와 같은 요청이 두 줄이 되지 않게), 요청 ID 를 같은 요청의 모든 로그에 붙이는 `request_id_var`·`RequestIdFilter`, 사용 로그 `log_event`(로거 `app.event`)
  - `app/core/config.py`: `LOG_FORMAT`(`json` 기본 / `text`)
  - `app/main.py`: `logging.basicConfig` → `configure_logging(settings.LOG_FORMAT)`
  - `app/core/middleware.py`: 받은 `X-Request-ID` 는 영문·숫자·`.`·`_`·`-` 128자 이하일 때만 쓰고 아니면 새로 만듦. 경로에서 처리하지 못한 예외는 **여기서 스택을 한 번 남기고 500 응답을 만든다**(다시 던지지 않음). Sentry 는 밖으로 나가는 예외를 잡는 방식이라 `sentry_sdk.capture_exception` 으로 직접 보냄. 요청 로그는 칸(`request_id`·`method`·`path`·`status`·`duration_ms`·`client`)으로, 5xx 는 ERROR, 1초 이상은 WARNING. 실행되지 않던 `HTTPException` 분기 삭제
  - `app/core/exceptions.py`: 500 응답 만들기를 `internal_error_response`(본문·헤더에 요청 ID)로 분리해 미들웨어와 같이 씀. `Exception` 처리기는 미들웨어 바깥에서 난 예외용으로 남기고 스택은 한 번만
  - `app/core/auth/deps.py`: 비상구가 꺼져 있을 때 Supabase 검증 실패도 `reason=` 으로 원인을 WARNING (토큰은 남기지 않음)
  - 사용 로그 (모두 commit 이후):
    - `booking/repository.py`: `booking.created`·`confirmed`·`declined`·`cancelled`·`cancel_requested`·`withdrawn`·`cancel_withdrawn`·`cancel_request_approved`·`cancel_request_declined`·`completed`·`no_show`. 완료·노쇼는 차감한 `customer_pass_id` 를 함께 남기고, 409 로 거부되면 `booking.complete_rejected`·`booking.no_show_rejected`(+ `reason`). 완료·노쇼 공통 부분을 `_use_lesson` 으로 묶음
    - `passes/repository.py`: `deduct_for_lesson` 이 차감한 수강권 id 를 돌려줌. `pass.assigned`·`pass.updated`(바뀐 칸 이름만, 메모 내용 제외)·`pass.sessions_added`
    - `payment/repository.py`·`router.py`: `payment.created`·`payment.status_changed`. 상태 변경에 처리한 관리자 ID 를 남기려고 `update_status` 에 `actor` 인자 추가 (router 는 이미 받던 관리자 값을 넘기기만 함)
  - 사람은 ID 로만 남긴다 (이메일·전화번호·토큰 없음). 클라이언트 IP 는 남긴다
  - 문서: `docs/operations/env-setup.md`(`LOG_FORMAT`), `troubleshooting.md` 14번(500 로그 찾는 법)
- 영향 범위 (API 계약, DB, 웹·앱):
  - API 응답 본문·상태 코드 변화 없음. 500 응답에 `X-Request-ID` 헤더가 새로 붙음
  - **500 응답에도 CORS 헤더가 붙는다**: 예전에는 500 이 CORS 미들웨어 바깥에서 만들어져 헤더가 없었고, 브라우저(두 앱 웹 빌드)에는 CORS 오류로 보였다(트러블슈팅 14번). 이제 미들웨어 안에서 500 을 만들므로 앱에서도 500 으로 보인다 (실제 uvicorn 으로 고치기 전·후 확인)
  - DB·마이그레이션 없음. 새 환경변수 `LOG_FORMAT` 은 기본값이 있어 Render·AWS 설정을 바꿀 필요 없음
- 커밋 / PR:

## 7. 결과 (고친 후)

- 같은 테스트의 실행 결과:

```text
$ make apitest ARGS="tests/test_logging.py -p no:randomly --tb=short"
.........                                                                [100%]
9 passed, 1 warning in 0.48s

$ make apitest
225 passed, 1 warning in 19.82s     (기존 216 + 이번 9)
```

- 실제 uvicorn 으로 확인 (로컬 더미 env, 일부러 예외를 던지는 임시 경로 `/__boom`, `LOG_FORMAT` 기본값 json). 긴 줄은 줄임:

```text
HTTP/1.1 500 Internal Server Error
x-request-id: a9c66c8a-ddfd-4a20-82b4-e9cf9cbcfa79
access-control-allow-origin: *            ← 고치기 전에는 없었다

{"level": "ERROR", "logger": "app.request", "message": "unhandled exception", "method": "GET", "path": "/__boom", "request_id": "a9c66c8a-...", "exc_info": "Traceback ..."}
{"level": "ERROR", "logger": "app.request", "message": "request", "request_id": "a9c66c8a-...", "method": "GET", "path": "/__boom", "status": 500, "duration_ms": 12.42, "client": "127.0.0.1"}
{"level": "INFO", "logger": "app.request", "message": "request", "request_id": "my-id-1", "method": "GET", "path": "/", "status": 200, "duration_ms": 1.43, "client": "127.0.0.1"}
```

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
| 500 하나당 스택 트레이스 | 3 (테스트) / 4 (uvicorn) | 1 | 위 임시 경로 |
| 500 응답의 `X-Request-ID` · CORS 헤더 | 없음 · 없음 | 있음 · 있음 | 같은 조건, `Origin: http://localhost:3000` |
| 같은 요청의 요청 로그 줄 | 2 (`app.request` + uvicorn 접근 로그) | 1 | 실제 uvicorn |

## 8. 남은 것

- 사용 로그는 거부(409)를 완료·노쇼만 남긴다. 다른 상태 전환(확정·취소 등)의 거부는 요청 로그의 `status=409` 로만 보인다
- 웹(Next.js 서버)·두 앱은 이번 범위 밖. 앱이 오류 화면에 `X-Request-ID` 를 보여 주면 사용자 문의 → 로그 찾기가 바로 이어진다 (409 이유 화면 표시 작업과 함께 볼 것)
- CloudWatch 에서 칸으로 거르는 쿼리(예: `status >= 500`, `duration_ms > 1000`, `event = "booking.completed"`)는 AWS 배포 재개 때 확인
- 느린 요청 기준 1초(`SLOW_REQUEST_MS`)는 정한 값이 아니라 출발점. 다음 작업(부하 테스트)의 p95 를 보고 조정

## 9. 배운 것

처음에는 테스트에서 500 오류 하나에 스택이 3번 찍히는 것을 보고, 그 중복만 없애면 된다고 생각했다. 그런데 실제 서버(uvicorn)로 띄워 보니 4번이었다. 테스트 도구는 서버가 예외를 다시 기록하는 마지막 단계를 거치지 않기 때문이다. 같은 확인 과정에서 500 응답에 CORS 헤더가 없다는 것도 발견했다. 500 이 CORS 처리 바깥에서 만들어져서, 앱에는 서버 오류가 아니라 CORS 오류로 보였던 것이고, 데모 장애 때 원인을 헷갈리게 만든 이유가 이것이었다. 그래서 미들웨어 안에서 500 을 직접 만들도록 바꿨고, 스택은 1번만 남고 요청 ID 와 CORS 헤더도 함께 붙었다. 테스트를 통과해도 실제 서버에서 한 번은 확인해야 하고, 오류 응답을 어디서 만드느냐가 사용자에게 보이는 증상까지 바꾼다는 것을 알았다.
