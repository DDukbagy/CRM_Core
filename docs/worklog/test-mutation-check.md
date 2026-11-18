# 기존 테스트 점검 (변이 테스트)

- 상태: 완료
- 기간: 2026-11-17 ~ 2026-11-18
- 브랜치 / PR: `crm`
- 관련 작업: [동시 요청 문제](pass-deduct-concurrency.md)

## 1. 문제

백엔드 테스트는 212개가 통과한다. 하지만 통과하는 테스트가 규칙을 실제로 지키고 있는지는 개수로 알 수 없다. 테스트가 응답 코드만 보거나, 규칙이 깨져도 결과가 같은 데이터만 쓰면 규칙이 깨져도 아무도 모른다.

그래서 결제·수강권·예약·프로모션(거래성 도메인)의 핵심 규칙을 한 줄씩 일부러 망가뜨리고(변이), 테스트가 실패하는지 본다.

- 테스트가 실패하면 → 그 규칙을 지키는 테스트가 있다 (잡힘)
- 테스트가 통과하면 → 규칙이 깨져도 모른다 (놓침) → 보강 대상

변이를 만드는 기준:

- 문법이 깨지지 않게 바꾼다. 서버가 정상으로 떠야 "규칙만 깨진 상태"를 시험할 수 있다
- 한 번에 규칙 하나만 깨뜨린다. 같은 규칙이 두 곳에 있으면 두 곳을 함께 바꾼다
- 매번 원래 코드로 되돌리고, 끝나면 `git status` 로 바뀐 파일이 없는지 확인한다

### 점검할 규칙 (25개)

줄 번호는 `63e4a69` 기준.

**수강권** (`backend/app/domains/passes/repository.py`)

| # | 규칙 | 위치 | 변이 | 결과 |
|---|---|---|---|---|
| P1 | 잔여 횟수를 넘겨 차감하지 않는다 | `deduct_for_lesson` 181·192줄 `CustomerPass.sessions_used < CustomerPass.sessions_total` | 두 곳 모두 `<` → `<=` | 살아남음 — 이중 방어 (아래 3절) |
| P2 | 마지막 회차를 쓰면 수강권이 완료(COMPLETED)된다 | `deduct_for_lesson` 198줄 `CustomerPass.sessions_used + 1 >= CustomerPass.sessions_total` | `>=` → `>` | 잡힘 (1개 실패: `test_completing_lesson_deducts_one_session`) |
| P3 | 쓸 수 있는 수강권이 없으면 완료·노쇼가 409 | `deduct_for_lesson` 206·207줄 `if res.first() is None: raise …409` | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만`) |
| P4 | 그 강사의 수강권에서만 차감한다 | `deduct_for_lesson` 179줄 `CustomerPass.instructor_id == instructor_id,` | 줄 삭제 | **살아남음 — 테스트 빈틈** |
| P5 | 수동 수정 때 사용 횟수가 총 횟수를 넘을 수 없다 | `update_customer_pass` 141·142줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_sessions_used_cannot_exceed_total`) |
| P6 | 추가 횟수는 1 이상 | `add_sessions` 154·155줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_using_all_sessions_completes_and_adding_reactivates`) |
| P7 | 완료된 수강권에 횟수를 추가하면 다시 사용 중이 된다 | `add_sessions` 159·160줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_using_all_sessions_completes_and_adding_reactivates`) |
| P8 | 사용 중인 수강권이 있는 상품은 삭제할 수 없다 (409) | `delete_type` 71·72줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_pass_type_with_active_customer_pass_cannot_be_deleted`) |
| P9 | 비활성 상품은 발급할 수 없다 | `assign` 104·105줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_assign_rules`) |
| P10 | 강사는 담당 고객에게만 발급한다 | `assign` 110·111줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_assign_rules`) |

**예약** (`backend/app/domains/booking/repository.py`)

| # | 규칙 | 위치 | 변이 | 결과 |
|---|---|---|---|---|
| B1 | 시간대의 요일이 아니면 예약할 수 없다 | `create` 124·125줄 | `if` 두 줄 삭제 | 살아남음 — 이중 방어 |
| B2 | 비활성 시간대는 예약할 수 없다 | `create` 122·123줄 | `if` 두 줄 삭제 | 살아남음 — 이중 방어 |
| B3 | 휴무·닫힌 시간은 예약할 수 없다 | `create` 132~134줄 | `if` 블록 삭제 | 잡힘 (3개 실패: `test_recurring_off_day`, `test_temporary_off_day`, `test_customer_cannot_book_blocked_time`) |
| B4 | 취소된 예약 자리는 다시 예약할 수 있다 | `_active_exists` 167줄 `Booking.status != "CANCELLED",` | 줄 삭제 | 잡힘 (2개 실패: `test_decline_and_withdraw_reopen_slot`, `test_cancel_then_rebook_allowed`) |
| B5 | 완료하면 수강권이 차감된다 | `complete` 254줄 `await self._deduct_pass(booking)` | 줄 삭제 | 잡힘 (5개 실패: `test_completed_and_no_show_lessons_use_pass_sessions`, `test_spec4_같은_예약_완료_N번_동시_1회만_차감`, `test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감` 외 2개) |
| B6 | 노쇼도 수강권이 차감된다 | `mark_no_show` 263줄 `await self._deduct_pass(booking)` | 줄 삭제 | 잡힘 (3개 실패: `test_completed_and_no_show_lessons_use_pass_sessions`, `test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감`, `test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만`) |
| B7 | 다른 강사는 내 예약을 처리할 수 없다 | `complete` 252줄 `await self.ensure_host_can_manage(booking, host)` | 줄 삭제 | **살아남음 — 테스트 빈틈** |
| B8 | 신청 중(REQUESTED)인 예약만 고객이 수정한다 | `update_by_guest` 178·179줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_full_lesson_lifecycle`) |
| B9 | 상태 전환은 기대한 상태일 때만 (동시 요청) | `_transition` 318줄 `Booking.status == expected` | 조건 삭제 (`where(Booking.id == booking.id)`) | 잡힘 (2개 실패: `test_spec4_같은_예약_완료_N번_동시_1회만_차감`, `test_spec1_확정과_신청_철회_동시_하나만_성공`) |

**결제** (`backend/app/domains/payment/repository.py`)

| # | 규칙 | 위치 | 변이 | 결과 |
|---|---|---|---|---|
| Y1 | 결제 금액은 0원보다 커야 한다 | `create` 33줄 `if data.amount <= 0:` | `<= 0` → `< 0` | 잡힘 (1개 실패: `test_invalid_payment_is_rejected[payload1-400]`) |
| Y2 | 허용된 결제 수단만 받는다 | `create` 30·31줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_invalid_payment_is_rejected[payload0-400]`) |
| Y3 | 강사는 담당 고객의 결제만 등록한다 | `create` 42·43줄 | `if` 두 줄 삭제 | 잡힘 (1개 실패: `test_instructor_cannot_record_payment_for_unmanaged_customer`) |

**프로모션** (`backend/app/domains/promotions/repository.py`)

| # | 규칙 | 위치 | 변이 | 결과 |
|---|---|---|---|---|
| R1 | 시작일 당일부터 진행 중이다 | `promotion_status` 21줄 `if today < p.start_date:` | `<` → `<=` | 잡힘 (2개 실패: `test_promotion_crud_and_customer_view`, `test_today_is_korean_date`) |
| R2 | 종료일 당일까지 고객에게 보인다 | `list_ongoing` 73줄 `Promotion.end_date >= today,` | `>=` → `>` | **살아남음 — 테스트 빈틈** |
| R3 | 종료일은 시작일보다 늦어야 한다 | `update` 111·112줄 | `if` 두 줄 삭제 | **살아남음 — 테스트 빈틈** (DB 제약이 데이터는 지킴) |

P1~P3 은 사용자가 직접, 나머지는 같은 방식으로 스크립트로 돌린다.

## 2. 테스트 명세

살아남은 변이 중 테스트 빈틈 4개를 골라 적었다.

- [ ] 확정된 예약을 다른 강사가 완료 처리하면 -> 본인이 신청한 수강권의 소유자인 강사만 완료할 수 있다
- [ ] A강사(먼저 구매)의 수강권과 B강사(나중에 구매)의 수강권이 같이 있을때 B강사가 수업을 완료처리하면 -> A강사의 수강권은 그대로 있고 B강사의 수강권이 차감되어야 한다
- [ ] 강사가 올린 프로모션은 -> 강사가 설정한 종료일 당일에도 노출되어 있는다
- [ ] 강사가 프로모션을 수정할 때 종료일이 시작일보다 빠르다면 -> 422, DB 오류 원문은 나가지 않는다

## 3. 재현 (고치기 전)

이 작업에서 "재현"은 변이를 넣어도 테스트가 통과하는 것이다.

- 실행한 명령: 변이 실행 스크립트로 25개를 하나씩 적용 → 문법 확인 → `poetry run pytest -q`(백엔드 테스트 212개 전체) → 결과 기록 → 원래 코드로 복원. 바꿀 문장이 기대한 개수만큼 있는지 먼저 확인하고, 어떤 경우에도 원래 파일로 되돌린다 (끝난 뒤 `git status` 로 확인)
- 실행 환경: 로컬 Postgres 컨테이너 `crm_test` (`scripts/test_local.sh` 로 새로 만든 뒤 변이마다 재사용). 변이 없이 먼저 돌려 212 passed 확인
- 커밋: `63e4a69`
- P1 은 사용자가 직접 넣어 같은 결과(212 passed)를 먼저 확인했다

```text
P1: survived | 212 passed | 0 failed
P2: killed   | 1 failed, 211 passed
P3: killed   | 1 failed, 211 passed
P4: survived | 212 passed | 0 failed
P5: killed   | 1 failed, 211 passed
P6: killed   | 1 failed, 211 passed
P7: killed   | 1 failed, 211 passed
P8: killed   | 1 failed, 211 passed
P9: killed   | 1 failed, 211 passed
P10: killed  | 1 failed, 211 passed
B1: survived | 212 passed | 0 failed
B2: survived | 212 passed | 0 failed
B3: killed   | 3 failed, 209 passed
B4: killed   | 2 failed, 210 passed
B5: killed   | 5 failed, 207 passed
B6: killed   | 3 failed, 209 passed
B7: survived | 212 passed | 0 failed
B8: killed   | 1 failed, 211 passed
B9: killed   | 2 failed, 210 passed
Y1: killed   | 1 failed, 211 passed
Y2: killed   | 1 failed, 211 passed
Y3: killed   | 1 failed, 211 passed
R1: killed   | 2 failed, 210 passed
R2: survived | 212 passed | 0 failed
R3: survived | 212 passed | 0 failed
```

**결과: 25개 중 18개 잡힘, 7개 살아남음.** 살아남은 7개를 코드로 다시 확인해 둘로 나눴다.

**이중 방어 — 같은 규칙을 다른 코드가 지킨다 (3개)**

| # | 왜 살아남았나 |
|---|---|
| P1 | 차감 UPDATE 에 `CustomerPass.status == "ACTIVE"` 조건도 있다. 마지막 회차를 쓰면 바로 COMPLETED 가 되고(P2 자리), 수동 수정도 다 쓰면 COMPLETED 로 바꾸므로 API 로는 "ACTIVE 인데 다 쓴" 수강권을 만들 수 없다. 처음에 P1·P2·P3 을 한꺼번에 넣었을 때는 실패했는데, P2 때문에 상태 조건이 무너져 P1 이 드러난 것이다 |
| B1 | 예약 생성은 요일 검사 뒤에 `day_status()` 의 열린 시간(`open_slot_ids`)도 확인한다. 열린 시간은 처음부터 "켜진 슬롯 중 그 요일에 해당하는 것"만 담으므로(`calendar/repository.py` `day_status`), 요일 검사를 빼도 같은 400 이 난다. 오류 문구만 달라진다 |
| B2 | 위와 같다. 열린 시간이 `s.is_active` 인 슬롯만 담으므로 비활성 시간대 검사를 빼도 400 |

**테스트 빈틈 — 규칙이 깨져도 아무 테스트도 실패하지 않는다 (4개)**

| # | 깨지면 생기는 일 | 테스트가 못 잡은 이유 |
|---|---|---|
| P4 | 고객이 강사 A·B 의 수강권을 모두 갖고 있을 때, A 의 레슨을 완료하면 B 의 수강권이 차감될 수 있다 | 고객 한 명이 여러 강사의 수강권을 가진 테스트가 없다 |
| B7 | 다른 강사가 내 예약을 완료 처리하고 고객 수강권을 차감할 수 있다 (권한) | 다른 강사의 완료 요청을 시험하는 테스트가 없다 |
| R2 | 종료일 당일에 진행 중인 프로모션이 고객 수강권 탭에서 사라진다 | 종료일 당일을 시험하는 테스트가 없다 (시작일 당일은 R1 이 잡힘) |
| R3 | 수정할 때 종료일을 시작일보다 앞으로 바꾸면, 422 대신 DB 제약(`ck_promotions_period`)이 막아 400 과 DB 오류 원문(`Database integrity error.` + 제약 이름)이 응답에 나간다. 데이터는 DB 가 지킨다 | 생성은 스키마 검사가 있어 테스트가 있지만, 수정 경로의 기간 검사 테스트가 없다 |

## 4. 원인

테스트가 "규칙이 깨졌을 때와 결과가 같은 데이터"만 쓰고 있었다.

- P4: 모든 차감 테스트가 고객 한 명에 강사 한 명의 수강권만 둔다. 수강권이 그 강사의 것뿐이면 강사 조건이 있든 없든 같은 수강권이 차감된다
- B7: 완료 테스트는 모두 예약을 받은 강사 본인이 요청한다. 다른 강사가 요청하는 경우가 없어 권한 확인을 빼도 결과가 같다
- R2: 진행 중 목록 테스트는 종료일이 한참 남은 프로모션만 쓴다. 경계(종료일 당일)를 시험하지 않는다. 시작일 쪽 경계는 `test_today_is_korean_date` 가 잡는다 (R1)
- R3: 기간 검사 테스트는 생성(`POST /promotions`)만 있다. 생성은 스키마(`PromotionCreate` 의 검사)도 막지만, 수정은 저장소 코드 한 곳만 막는다. 그 한 곳을 빼면 DB 제약이 데이터는 지키지만 응답이 400 과 DB 오류 원문으로 바뀌는데, 이를 시험하는 테스트가 없었다

## 5. 선택지와 결정

| 선택지 | 장점 | 단점 |
|---|---|---|
| A. 테스트 빈틈 4개(P4·B7·R2·R3)만 보강 | 실제로 규칙이 깨져도 모르는 곳만 막는다. 작업이 작다 | 이중 방어 3개는 "다른 코드"가 바뀌면 다시 빈틈이 된다 |
| B. 이중 방어 3개(P1·B1·B2)까지 보강 | 나중에 방어 코드가 바뀌어도 테스트가 남는다 | 지금은 규칙이 지켜지는 곳이라, 그 테스트가 무엇을 지키는지 설명하기 어렵다 (변이를 넣어도 다른 코드 때문에 통과) |
| C. 도구(mutmut 등)로 전체 변이 | 빠짐없이 훑는다 | DB 테스트라 오래 걸리고 의미 없는 변이가 많다. 패키지 설치 필요 |

- 고른 것: A. 테스트 빈틈 4개만 보강
- 이유: 이번에는 규칙이 깨져도 아무 테스트도 모르는 곳만 막는 데 집중했다. 이중 방어 3개는 지금도 다른 코드가 같은 규칙을 지키고 있어 당장 위험하지 않으므로, 그 방어 코드를 바꾸게 될 때 함께 보강한다.

## 6. 수정

이 작업은 코드를 고치지 않고 테스트만 더한다. 코드는 이미 규칙을 지키고 있었다.

- 바꾼 파일:
  - `backend/tests/test_passes.py`: 명세 1(B7) `test_other_instructor_cannot_complete_booking`, 명세 2(P4) `test_completion_deducts_only_that_instructors_pass`. 도우미 `_confirmed_booking`·`_issue_pass`·`_pass_state`·`_booking_status`. 응답뿐 아니라 요청 뒤 DB 의 예약 상태·수강권 사용 횟수를 직접 읽어 확인한다. 명세 1 의 "다른 강사" 는 캘린더도 다르고 그 고객에게 수강권도 발급하지 않은 강사로 만들었다 (캘린더 기준·수강권 기준 어느 쪽으로 봐도 다른 강사). 명세 2 는 A 를 먼저 발급해 강사 조건이 빠지면 A 가 차감되게 했다
  - `backend/tests/test_promotions_dashboard.py`: 명세 3(R2) `test_promotion_is_shown_on_its_end_date`, 명세 4(R3) `test_update_with_end_before_start_is_422`
- 영향 범위 (API 계약, DB, 웹·앱): 없음 (테스트만)
- 커밋 / PR: `crm` 브랜치 한 커밋 (테스트·문서)

## 7. 결과 (고친 후)

- 새 테스트를 더한 뒤 백엔드 전체: `make apitest` 216 passed (212 + 4)
- 살아남았던 변이 4개를 같은 방식으로 다시 넣었더니 모두 잡혔고, 각각 새 테스트가 잡았다:

```text
B7: killed | 1 failed, 215 passed | test_other_instructor_cannot_complete_booking
P4: killed | 1 failed, 215 passed | test_completion_deducts_only_that_instructors_pass
R2: killed | 1 failed, 215 passed | test_promotion_is_shown_on_its_end_date
R3: killed | 1 failed, 215 passed | test_update_with_end_before_start_is_422
```

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
| 핵심 규칙 변이 25개 중 테스트가 잡은 것 | 18 | 22 | 로컬 Postgres `crm_test`, 변이 하나씩, 백엔드 테스트 전체 |
| 테스트 빈틈 (규칙이 깨져도 모름) | 4 | 0 | 같음 |
| 이중 방어로 살아남은 것 (규칙은 지켜짐) | 3 | 3 | 같음 |

## 8. 남은 것

- 이중 방어 3개(P1·B1·B2)는 보강하지 않았다. 방어하는 다른 코드(`status == "ACTIVE"` 조건, `day_status()` 의 열린 시간)가 바뀌면 다시 빈틈이 될 수 있다
- 25개는 손으로 고른 핵심 규칙이다. 고르지 않은 규칙(같은 강사의 수강권이 여러 개일 때 먼저 발급된 것부터 차감, 결제 상태 변경, 보존 기간 삭제 등)은 점검하지 않았다
- 변이 실행 스크립트는 저장소에 남기지 않았다. 다시 할 때는 1절 표의 위치·변이대로 하나씩 넣고 `make apitest` 를 돌리면 된다
- 명세 1 의 권한은 지금 캘린더 주인으로 확인한다. 예약에 수강권을 고정하는 작업(개선 6번)에서 수강권 기준이 함께 들어가면 이 테스트도 다시 본다

## 9. 배운 것

처음에는 테스트 212개가 모두 통과하니 핵심 규칙도 다 지켜지고 있다고 생각했다. 그런데 규칙을 한 줄씩 일부러 망가뜨려 보니, 25개 중 4개는 망가뜨려도 아무 테스트도 실패하지 않았다. 테스트가 "규칙이 깨져도 결과가 같은 데이터"(강사 한 명, 본인 요청, 경계일 없음)만 쓰고 있었기 때문이다. 그래서 다른 강사의 수강권을 먼저 발급해 두는 것처럼, 규칙이 깨지면 결과가 달라지는 데이터를 일부러 만들어 보강했다(18/25 → 22/25). 테스트의 가치는 개수가 아니라 규칙이 깨졌을 때 실패하느냐에 있다는 것을 알았다.
