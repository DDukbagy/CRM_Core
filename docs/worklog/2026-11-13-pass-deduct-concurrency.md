포트# 수강권 차감·예약 상태 전환의 동시 요청 문제

- 상태: 진행 중
- 기간: 2026-11-13 ~
- 브랜치 / PR:
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

왜 이런 일이 생기는가. 관련 파일과 함수.

## 5. 선택지와 결정

| 선택지 | 장점 | 단점 |
|---|---|---|
|  |  |  |
|  |  |  |

- 고른 것:
- 이유:

## 6. 수정

- 바꾼 파일:
- 영향 범위 (API 계약, DB, 웹·앱):
- 커밋 / PR:

## 7. 결과 (고친 후)

- 같은 테스트의 실행 결과:

```text
(통과 출력을 그대로 붙여 넣기)
```

- 측정값이 있으면 조건과 함께:

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
|  |  |  |  |

## 8. 남은 것

못 한 것, 한계, 다음에 볼 것.

## 9. 배운 것 (사용자가 작성)

면접에서 이 작업을 설명한다면 할 말. (서너 줄)
