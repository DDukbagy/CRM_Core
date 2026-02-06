# AWS & Copilot 운영 가이드

> ⚠️ 이 문서는 **기존 문서를 변경하지 않고**, AWS/Copilot 운영 관련 내용을 **추가 문서로 분리**한 것입니다.

---

## 1. 이 문서의 목적

이 문서는 다음을 빠르게 다시 떠올릴 수 있도록 만든 **운영자용 실전 가이드**입니다.

* AWS 자격증명 개념 정리
* Copilot 기반 환경(staging/prod) 구조 이해
* 자주 쓰는 명령어 모음
* 장애/배포 시 실제 행동 순서

---

## 2. CI / Staging / Prod 개념 정리 (우리 프로젝트 기준)

### CI (Continuous Integration)

* 목적: **코드 자체 검증**
* 수행 내용:

  * 테스트
  * 린트
  * 타입체크
  * 빌드 가능 여부
* 실행 위치: GitHub Actions
* 트리거: PR 생성 / PR 업데이트

👉 CI는 **코드가 문제없는지**만 본다.

---

### Staging

* 목적: **운영 리허설 환경**
* 특징:

  * AWS 상에 실제 인프라(ECS, ALB, IAM 등)
  * prod와 거의 동일한 구성
  * 고객 트래픽은 없음

👉 CI를 통과한 코드가 **실제 AWS 환경에서 잘 도는지** 확인

---

### Production (prod)

* 목적: 실제 서비스 운영
* 특징:

  * 승인 후에만 배포
  * 고객이 실제로 접근

---

### 전체 흐름 요약

1. PR 생성 → CI 자동 실행
2. CI 통과 → main merge
3. main merge → **staging 자동 배포**
4. staging 확인 OK → **승인**
5. prod 배포 → 운영 반영

---

## 3. AWS 자격증명 구조 (중요)

### Access Key ID ≠ Account ID

* ❌ Account ID: `123456789012` (12자리 숫자)
* ✅ Access Key ID: `AKIA...` 또는 `ASIA...`

Copilot / AWS CLI에서 필요한 것은 **Access Key ID + Secret Access Key**

---

### 자격증명 사용 방식

#### 로컬 / Codespace

* `aws configure`로 한 번 저장
* 또는 AWS SSO 사용

#### GitHub Actions

* OIDC 또는 Secrets 사용
* 로컬 키와 분리 권장

---

### 현재 로그인 상태 확인

```bash
aws sts get-caller-identity
```

---

## 4. Copilot 환경 구조

### 환경(Environment)

* prod
* staging

각 환경은:

* 별도 VPC
* 별도 ECS Cluster
* 별도 IAM Role

---

### 서비스(Service)

* api

각 서비스는 환경별로 **별도 배포**됨:

```bash
copilot svc deploy --name api --env staging
copilot svc deploy --name api --env prod
```

---

## 5. 자주 쓰는 Copilot 명령어

### 환경 확인

```bash
copilot env ls
copilot env status --name staging
copilot env status --name prod
```

---

### 서비스 상태

```bash
copilot svc ls
copilot svc status --name api --env staging
copilot svc status --name api --env prod
```

---

### 로그 확인

```bash
copilot svc logs --name api --env staging --follow
copilot svc logs --name api --env prod --since 1h
```

---

### 컨테이너 접속

```bash
copilot svc exec --name api --env staging
```

---

## 6. 장애 발생 시 체크 순서 (실전)

1. CI 통과 여부 확인
2. staging 배포 성공 여부 확인
3. `copilot svc status`
4. `copilot svc logs`
5. 환경변수 / 시크릿 확인
6. 필요 시 task exec 접속

---

## 7. 정리

* CI = 코드 검증
* staging = 운영 리허설
* prod = 실제 서비스
* 배포는 **의도적으로 두 번** 한다

이 문서는 **운영 판단을 빠르게 하기 위한 체크리스트**로 유지한다.
