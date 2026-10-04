# PG(온라인 결제) 연동 방법

> 상태: **미연동** (배포 후 진행). 지금 고객 앱 수강권 탭의 "수강권 결제하기"는 "결제 준비 중" 안내만 띄운다.
> 결제는 강사·관리자가 직접 기록한다(`POST /payments`, 현금·계좌이체 등).
> 이 문서는 토스페이먼츠를 예로 든다. 포트원(아임포트)을 쓰면 4장 표를 참고한다. PG사 API 의 정확한 필드·URL 은 연동 시점의 공식 문서로 다시 확인한다.

---

## 1. 돈이 나가나? — 테스트 모드

| 단계 | 키 | 실제 청구 | 필요한 것 |
|---|---|---|---|
| 테스트 | 테스트 키 (`test_ck_…`, `test_sk_…`) | **없음.** 승인·취소 흐름만 실제와 같음 | PG사 개발자센터 가입 |
| 운영 | 라이브 키 (`live_…`) | 있음 | 사업자 등록 + PG사 심사·계약 (보통 수 일~수 주) |

- 개발·포트폴리오 단계는 테스트 키로 끝까지 만들 수 있다. 라이브 키는 계약 전에는 발급되지 않는다.
- 테스트 결제 내역은 PG사 개발자센터의 테스트 결제 내역에서 확인한다.

---

## 2. 전체 흐름

```text
[고객 앱/웹]            [백엔드 FastAPI]                      [PG사]
 1. 수강권 선택 ──────▶ 2. 주문 생성 (금액은 서버가 계산)
                         payments: PENDING, order_id 발급
            ◀────────── orderId, amount, orderName
 3. PG 결제창 열기 (clientKey) ─────────────────────────────▶ 카드·간편결제 인증
            ◀───────────────────────────────── successUrl?paymentKey&orderId&amount
 4. 결과 전달 ────────▶ 5. 승인 요청 (secretKey, 서버만) ──▶ 승인
                         금액이 PENDING 금액과 같은지 확인
                         COMPLETED + pg_payment_id 저장
                         + 수강권 발급 (한 트랜잭션)
            ◀────────── 결제 완료, 발급된 수강권
                       6. 웹훅 (취소·가상계좌 입금 등) ◀──── 상태 변경 알림
```

핵심 규칙

- **금액은 서버가 정한다.** 클라이언트가 보낸 금액을 믿지 않는다. 수강권 상품 가격과 진행 중 프로모션(`promotions`)으로 서버가 계산하고 PENDING 결제에 저장한다. 승인 때 PG 가 돌려준 금액과 비교한다.
- **승인은 서버에서만** 한다. secret key 는 백엔드 env 에만 둔다.
- **한 주문은 한 번만 승인**한다(멱등). 같은 `order_id` 로 두 번 오면 두 번째는 저장된 결과를 그대로 돌려준다.
- **승인 성공과 수강권 발급은 한 트랜잭션.** 발급이 실패하면 PG 결제를 취소하고 FAILED 로 남긴다.

---

## 3. 이 저장소에서 바꿀 곳

### 3.1 DB (마이그레이션 1개)

`payments` 에는 이미 `status`(PENDING·COMPLETED·FAILED·REFUNDED), `method`(TOSS·KAKAO·NAVER…), `pg_payment_id`, `customer_pass_id` 가 있다. 추가할 것:

| 컬럼 | 용도 |
|---|---|
| `order_id` (VARCHAR, UNIQUE) | PG 에 넘기는 주문 번호. 멱등 처리 기준 |
| `pass_type_id` (INT, FK lesson_pass_types SET NULL) | 무엇을 사려는지 (승인 후 수강권 발급에 사용) |
| `promotion_id` (INT, FK promotions SET NULL, 선택) | 적용한 할인 |
| `failure_reason` (TEXT, 선택) | 실패·취소 사유 |

순서는 CLAUDE.md §9.4 를 따른다: 모델 → 마이그레이션 → 로컬 검증 → 원격 리허설 → 승인 후 적용.

### 3.2 백엔드 (`domains/payment/`)

| API | 하는 일 |
|---|---|
| `POST /payments/orders` (고객) | `pass_type_id` 를 받아 담당 강사의 상품인지 확인 → 진행 중 프로모션 반영해 금액 계산 → PENDING 결제 생성 → `orderId`·`amount`·`orderName` 응답 |
| `POST /payments/confirm` (고객) | `paymentKey`·`orderId`·`amount` 를 받아 PENDING 과 금액 비교 → PG 승인 API 호출 → COMPLETED + `pg_payment_id` + `PassRepository` 로 수강권 발급 |
| `POST /payments/webhook` (PG → 서버) | 결제 취소·입금 등 상태 변경. **본문을 믿지 말고** `paymentKey` 로 PG 조회 API 를 다시 불러 확인한 뒤 반영 |
| `PATCH /payments/{id}/status` (기존) | 환불 시 PG 취소 API 호출로 확장 (현재 보류 중인 "결제 상태 변경") |

- PG 호출은 `repository.py` 안에서 `httpx.AsyncClient` 로 한다(async 규칙). router 에는 넣지 않는다.
- 토스페이먼츠 승인 API(예): `POST https://api.tosspayments.com/v1/payments/confirm`, Basic 인증(`secretKey:` 를 base64), 본문 `{paymentKey, orderId, amount}`
- 취소 API(예): `POST https://api.tosspayments.com/v1/payments/{paymentKey}/cancel`, 본문 `{cancelReason}`
- 로그에 키·카드 정보를 남기지 않는다. `paymentKey`·`orderId` 정도만

### 3.3 환경 변수 (이름만, 값은 PG 개발자센터에서)

| 위치 | 변수 | 공개 여부 |
|---|---|---|
| `backend/.env` | `TOSS_SECRET_KEY` | **비밀.** 서버만 |
| `backend/.env` | `TOSS_WEBHOOK_SECRET` (웹훅 서명을 쓰는 경우) | 비밀 |
| `frontend/.env.local` | `NEXT_PUBLIC_TOSS_CLIENT_KEY` | 공개 가능 (client key) |
| `apps/customer/.env` | `EXPO_PUBLIC_TOSS_CLIENT_KEY` | 공개 가능 |

새 env 이름을 쓰기 전에 각 폴더 `.env.example` 에 이름만 추가하고, `.gitignore` 에 실제 파일이 걸리는지 확인한다(CLAUDE.md §4.3).

### 3.4 클라이언트

| 클라이언트 | 방법 |
|---|---|
| 고객 앱 (Expo) | "수강권 결제하기" → `POST /payments/orders` → 결제창을 `react-native-webview` 로 열기(토스 결제위젯 페이지 또는 웹 결제 페이지). 성공·실패 URL 은 앱 딥링크(`scheme://payments/success`) 또는 웹 페이지 → 앱 복귀 후 `POST /payments/confirm`. 카드사 앱 전환(app-to-app) 처리가 필요해서 PG 의 React Native 가이드를 따른다 |
| 웹 (필요 시) | PG JS SDK(예: `@tosspayments/tosspayments-sdk`)로 결제창 → successUrl 페이지에서 `/api/payments/confirm`(Next 프록시 경유, CLAUDE.md 규칙) |
| 강사 앱·웹 | 변화 없음. 매출 분석(`/instructors/me/dashboard`)이 COMPLETED 결제를 그대로 집계 |

- 현재 프로모션은 "안내용"이다. 연동하면서 2번(주문 생성)에서 실제 할인으로 적용한다.

---

## 4. 토스페이먼츠 vs 포트원

| | 토스페이먼츠 직접 | 포트원(아임포트) |
|---|---|---|
| 연동 대상 | 토스페이먼츠 하나 | 여러 PG(토스·KG이니시스·카카오페이 등)를 한 API 로 |
| 앱 | WebView + 딥링크 직접 처리 | React Native 용 모듈 제공 (웹뷰·앱 전환 처리 포함) |
| 서버 승인 | `/v1/payments/confirm` | 결제 후 포트원 API 로 결제 조회·검증 |
| 장점 | 구조가 단순, 문서가 좋음 | PG 교체·추가가 쉬움, 앱 처리 부담이 적음 |
| 추천 상황 | PG 하나로 충분할 때 | 간편결제 여러 개를 붙이거나 앱 연동 부담을 줄이고 싶을 때 |

어느 쪽이든 2장의 핵심 규칙(서버 금액 계산·서버 승인·멱등·한 트랜잭션)은 같다.

---

## 5. 테스트 계획

1. **pytest**: PG 호출을 가짜 응답으로 바꿔서(httpx 를 monkeypatch) 다음을 확인
   - 금액 불일치 거절
   - 같은 주문 두 번 승인 → 한 번만 처리
   - 승인 성공 → 수강권 발급
   - 발급 실패 → 결제 취소 호출 + FAILED
   - 웹훅 재조회
   - 결제·수강권은 거래성 도메인이라 테스트 필수(CLAUDE.md §6)
2. **로컬 화면**: 테스트 키로 결제창 → 테스트 카드 → 승인 → 고객 수강권 탭에 발급 확인
3. **스테이징**: 배포 후 웹훅 주소를 PG 개발자센터에 등록하고 취소·환불까지 한 번
4. **라이브 전환**: 키만 바꾼다(코드 변경 없음). 첫 실결제는 소액으로 하고 바로 환불까지 확인
