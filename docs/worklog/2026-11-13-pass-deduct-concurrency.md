포트# 수강권 차감·예약 상태 전환의 동시 요청 문제

- 상태: 진행 중
- 기간: 2026-11-13 ~
- 브랜치 / PR: `crm`
- 관련 작업:

## 1. 문제

예약 상태 전환(`confirm`, `withdraw_by_guest`, `complete`, `mark_no_show`)과 수강권 차감(`deduct_for_lesson`)이 모두 "읽고 → 확인 → 저장" 방식이라, 동시에 들어온 요청을 막지 못한다.

- 신청 중(REQUESTED)인 예약에 강사의 확정과 고객의 신청 철회가 동시에 오면, 둘 다 REQUESTED 를 읽고 통과해 나중에 저장한 쪽이 이긴다. 고객은 "예약 확정" 알림을 받았는데 예약은 취소돼 있는 식으로 상태가 어긋날 수 있다.
- 같은 수강권을 쓰는 서로 다른 예약 두 건이 동시에 완료되면 차감 1회가 사라질 수 있다 (갱신 손실).
- 같은 예약에 완료 요청이 두 번 오면 이중 차감될 수 있다. 화면의 버튼 잠금은 한 화면 안에서만 막으므로, 웹·앱 동시 사용이나 응답 지연 후 재시도 때는 요청이 겹칠 수 있다.

코드 검토로 확인했고, 행 잠금·조건부 UPDATE·동시 요청 테스트가 모두 없다. 실제 증상은 아래 테스트로 확인한다.

## 2. 테스트 명세 (사용자가 작성)

검증할 규칙을 한 줄씩 적는다. "어떤 상황에서 → 무엇이 일어나야 한다" 형식.

- [ ] 강사의 확정 처리와 고객의 신청 철회가 동시에 들어오면 -> 먼저처리가 된 요청이 우선이어야하고 나중에 처리가 된 요청은 409를 반환하게 한다.
- [ ] 한 고객의 서로 다른 예약의 완료처리(노쇼포함) 2번이 동시에 들어오면 -> 수강권은 2번 차감이 되어야한다
- [ ] 잔여 1회 수강권으로 서로 다른 예약 2건(노쇼 포함)의 완료가 동시에 오면 → 1건만 완료·차감되고 나머지 1건은 409
- [ ] 같은 예약에 완료 요청 N번이 동시에 오면 -> 수강권은 1회만 차감된다, 나머지는 409

## 3. 재현 (고치기 전)

- 테스트 이름 또는 실행한 명령: `make apitest ARGS="tests/test_concurrency.py --tb=short -p no:logging -p no:cacheprovider"` (`backend/tests/test_concurrency.py` 4개, 명세 1~4 에 하나씩)
- 실행 환경: 로컬 Postgres 컨테이너 (`make apitest` 가 `crm_test` DB 를 새로 만들고 마이그레이션 적용). 요청마다 별도 DB 연결, 실제 commit
- 커밋: `3601b0d` (수정 전 코드) + 테스트 파일
- 재현 방법: `asyncio.gather` 로 요청을 동시에 보낸다. 처음에는 그것만으로 명세 2 가 우연히 통과했다(앞 요청이 몇 ms 먼저 끝나 겹치지 않음). 예약을 읽은 직후 요청들이 서로를 기다리게 하는 장치(`RaceGate`, `asyncio.Barrier`)를 넣은 뒤로는 3번 반복 모두 4개가 같은 이유로 실패했다.

```text
(요청 로그 줄은 생략)
=================================== FAILURES ===================================
_______________________ test_spec4_같은_예약_완료_N번_동시_1회만_차감 _______________________
tests/test_concurrency.py:220: in test_spec4_같은_예약_완료_N번_동시_1회만_차감
    assert codes == [200, 409, 409], f"Expected [200, 409, 409], but got {codes}"
E   AssertionError: Expected [200, 409, 409], but got [200, 200, 200]
E   assert [200, 200, 200] == [200, 409, 409]
E     
E     At index 1 diff: 200 != 409
E     Use -v to get more diff
_____________________ test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감 ______________________
tests/test_concurrency.py:242: in test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감
    assert await sessions_used(real_db, cp_id) == 2
E   assert 1 == 2
_____________________ test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만 _____________________
tests/test_concurrency.py:261: in test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만
    assert [r.status_code for r in responses] == [200, 409] or [r.status_code for r in responses] == [409, 200]
E   assert ([200, 200] == [200, 409]
E     
E     At index 1 diff: 200 != 409
E     Use -v to get more diff or [200, 200] == [409, 200]
E     
E     At index 0 diff: 200 != 409
E     Use -v to get more diff)
________________________ test_spec1_확정과_신청_철회_동시_하나만_성공 ________________________
tests/test_concurrency.py:288: in test_spec1_확정과_신청_철회_동시_하나만_성공
    assert [confirm_r.status_code, withdraw_r.status_code].count(200) == 1
E   assert 2 == 1
E    +  where 2 = <built-in method count of list object at 0x7293de311240>(200)
E    +    where <built-in method count of list object at 0x7293de311240> = [200, 200].count
=========================== short test summary info ============================
FAILED tests/test_concurrency.py::test_spec4_같은_예약_완료_N번_동시_1회만_차감
FAILED tests/test_concurrency.py::test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감
FAILED tests/test_concurrency.py::test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만
FAILED tests/test_concurrency.py::test_spec1_확정과_신청_철회_동시_하나만_성공
4 failed, 1 warning in 0.82s
```

| 명세 | 기대 | 실제 (고치기 전) | 뜻 |
|---|---|---|---|
| 1. 확정 + 신청 철회 동시 | 200 하나, 409 하나 | 200, 200 | 둘 다 성공. 나중에 저장한 쪽이 앞 결과를 덮어씀 |
| 2. 서로 다른 예약 2건 동시 (잔여 충분) | 2회 차감 | 1회 차감 | 갱신 손실: 차감 1회가 사라짐 |
| 3. 잔여 1회에 서로 다른 예약 2건 동시 | 200 하나, 409 하나 | 200, 200 | 차감 못 한 예약도 완료 처리됨 |
| 4. 같은 예약 완료 3번 동시 | 200 하나, 409 둘 | 200, 200, 200 | 세 요청 모두 완료 처리 |

## 4. 원인

모든 경로가 "읽고 → 애플리케이션에서 확인 → 저장" 이고, 읽은 뒤 저장할 때까지 다른 요청이 같은 행을 바꾸는 것을 막는 장치가 없다.

- 예약 상태 전환 (`backend/app/domains/booking/repository.py`): `get_or_404` 가 예약을 잠금 없이 읽고, `confirm`·`withdraw_by_guest`·`complete`·`mark_no_show` 가 Python 에서 `booking.status` 를 확인한 뒤 새 상태를 저장한다. 동시에 온 요청은 모두 이전 상태를 읽고 확인을 통과한다. 저장은 `UPDATE ... SET status = '새 상태' WHERE id = :id` 라서 나중에 저장한 쪽이 앞 결과를 덮어쓴다 (명세 1, 4).
- 수강권 차감 (`backend/app/domains/passes/repository.py` `deduct_for_lesson`): 활성 수강권을 잠금 없이 읽고 `sessions_used < sessions_total` 을 Python 에서 확인한 뒤 `sessions_used += 1` 한다. ORM 이 보내는 SQL 은 `SET sessions_used = 계산된 값` 이라, 두 요청이 같은 값을 읽으면 같은 값을 써서 차감 1회가 사라진다 (명세 2).
- 잔여 부족: 수강권이 없거나 다 썼으면 차감만 건너뛰고 완료는 그대로 진행한다 (명세 3). 정책상 409 로 거부해야 한다.
- 거부 응답: 상태가 맞지 않으면 400, 이미 같은 상태면 200 을 돌려준다. 정책은 409 통일.
- PostgreSQL 기본 격리 수준(READ COMMITTED)은 쿼리마다 그 시점에 커밋된 값을 보여 줄 뿐, 읽은 행을 다른 트랜잭션이 바꾸지 못하게 막지는 않는다. MySQL(InnoDB) 기본값 REPEATABLE READ 에서도 일반 SELECT 후 UPDATE 하는 이 패턴의 갱신 손실은 막히지 않는다.

## 5. 선택지와 결정

| 선택지 | 방식 | 장점 | 단점 |
|---|---|---|---|
| A. 조건부 UPDATE | 예약: `UPDATE bookings SET status = :새 WHERE id = :id AND status = :기대 RETURNING ...`, 바뀐 행이 0 이면 409. 차감: `UPDATE customer_passes SET sessions_used = sessions_used + 1 ... WHERE ... AND sessions_used < sessions_total`, 0 이면 409 (같은 트랜잭션이라 예약 상태 변경도 함께 롤백) | 확인과 저장이 SQL 한 문장이라 DB 가 보장한다. 잠금을 오래 잡지 않는다. 결제 웹훅 중복 처리 등 다른 곳에도 같은 방식을 쓸 수 있다 | 규칙 일부가 SQL 조건으로 옮겨간다. 바뀐 행 수를 꼭 확인해야 한다 |
| B. 비관적 락 | 상태를 바꾸는 경로에서 `SELECT ... FOR UPDATE` 로 예약·수강권 행을 잠그고 읽는다. 나중 요청은 앞 요청이 커밋할 때까지 기다렸다가 바뀐 상태를 보고 409 | 지금 코드 구조(읽고 → 확인 → 저장)를 거의 유지한다. 복잡한 확인도 Python 에서 그대로 할 수 있다 | 잠금 대기가 생긴다. 잠그는 순서가 경로마다 다르면 교착 상태 위험. 조회용 `get_or_404` 와 잠금용 읽기를 나눠야 한다. 테스트의 RaceGate(읽은 뒤 서로 기다림)와 맞지 않아 테스트 장치를 바꿔야 한다 |
| C. 낙관적 락 | `version` 컬럼을 두고 `WHERE version = :읽은 값` 으로 저장, 실패하면 409 또는 재시도 | 잠금 없음. 여러 컬럼을 고치는 경우에도 일반적으로 쓸 수 있다 | DB 마이그레이션 필요. 모든 저장 경로가 version 을 지켜야 한다 |
| D. 격리 수준 상향 | 해당 트랜잭션을 REPEATABLE READ / SERIALIZABLE 로 | 코드 변경이 적다 | 충돌 시 직렬화 오류가 나므로 재시도 로직이 필요하다. 영향이 넓고 동작을 예측하기 어렵다 |

- 고른 것: a 조건부 update
- 이유: 연산이 단순해서 굳이 무거운 락을 걸 필요없이 sql문으로 해결이 가능하기 때문에

## 6. 수정

- 바꾼 파일:
  - `backend/app/domains/booking/repository.py`: 상태 전환 10개(확정·거절·강사 취소·취소 신청·신청 철회·취소 신청 철회·취소 승인·취소 거절·완료·노쇼)를 `_transition` 하나로 처리. `UPDATE bookings SET status = :새 WHERE id = :id AND status = :기대 RETURNING id`, 바뀐 행이 0 이면 409. 상태가 맞지 않는 요청(이미 같은 상태 포함)은 모두 409. 푸시 알림은 성공한 요청만 보낸다
  - `backend/app/domains/passes/repository.py` `deduct_for_lesson`: `UPDATE customer_passes SET sessions_used = sessions_used + 1, status = CASE ... WHERE id = (먼저 발급된 활성 수강권) AND status = 'ACTIVE' AND sessions_used < sessions_total`, 바뀐 행이 0 이면 409. 예약 상태 변경과 같은 트랜잭션이라 차감이 실패하면 예약도 CONFIRMED 그대로
  - 기존 테스트(`test_booking_flow.py`, `test_bookings.py`): 정책 변경에 맞춰 400·200 기대값을 409 로, 수강권 없이 완료·노쇼하던 테스트에 수강권 추가
- 영향 범위 (API 계약, DB, 웹·앱):
  - API 계약: 응답 형태는 그대로, 상태 코드만 바뀜. 상태 전환 요청의 잘못된 전환 400 → 409, 이미 같은 상태 200 → 409, 쓸 수 있는 수강권 없이 완료·노쇼 200 → 409. 입력값 오류·내용 수정 거부는 400 그대로
  - DB: 스키마·마이그레이션 변경 없음
  - 웹·앱: 타입 변경 없음. 지금도 400·409 를 같은 일반 메시지("처리 실패", "API Error")로 보여 주므로 깨지지 않는다. 거부 이유를 화면에 보여 주는 개선은 별도 작업
- 커밋 / PR: `807a7e1` (test: 재현) → fix 커밋 (아래 PR)

## 7. 결과 (고친 후)

- 같은 테스트의 실행 결과 (3번 반복 모두 같음):

```text
=========================== short test summary info ============================
PASSED tests/test_concurrency.py::test_spec4_같은_예약_완료_N번_동시_1회만_차감
PASSED tests/test_concurrency.py::test_spec2_서로_다른_예약_완료와_노쇼_동시_2회_차감
PASSED tests/test_concurrency.py::test_spec3_잔여_1회에_서로_다른_예약_2건_동시_1건만
PASSED tests/test_concurrency.py::test_spec1_확정과_신청_철회_동시_하나만_성공
4 passed, 1 warning in 0.74s
```

- 백엔드 전체: `make apitest` 207 passed. `make check`(백엔드·웹 lint·타입, 두 앱 타입) 통과

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
| 명세 1~4 동시 요청 테스트 | 4 failed | 4 passed | 로컬 Postgres 컨테이너, 요청마다 별도 연결, RaceGate 로 경쟁 강제, 3회 반복 |

## 8. 남은 것

- 같은 강사의 수강권이 여러 개일 때 먼저 발급된 것부터 차감한다. 앞 수강권이 동시 요청으로 방금 소진되면 다른 수강권이 남아 있어도 나중 요청은 409 가 될 수 있다. 예약 시 수강권 고정 작업에서 해결
- 수강권 횟수 추가·수동 수정이 차감과 겹치는 경우는 이번 범위 밖 (별도 작업)
- 예약 생성 시 서버가 수강권을 확인하지 않는다 (별도 작업)
- 웹·앱이 409 의 이유(잔여 없음, 이미 처리됨)를 화면에 보여 주지 않는다 (별도 작업)
- 테스트의 RaceGate 는 `BookingRepository.get_or_404` 뒤에 끼운다. 읽는 함수 이름이 바뀌면 테스트 장치도 함께 바꿔야 한다

## 9. 배운 것 (사용자가 작성)

면접에서 이 작업을 설명한다면 할 말. (서너 줄)
