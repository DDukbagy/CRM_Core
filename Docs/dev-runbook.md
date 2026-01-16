# Dev Runbook (개발 명령어 모음)

이 문서는 **개발/운영 중 자주 쓰는 명령어를 정리한 실행 가이드**입니다.

---

## 1. 서버 실행

```bash
make server
```

* 내부 명령:

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 2. 원클릭 검증 (추천)

```bash
make verify
```

동작 순서:

1. 서버가 켜져 있으면 그대로 사용
2. 꺼져 있으면 자동 실행
3. 토큰 발급 (`dev_tokens.sh`, `load_tokens.sh`)
4. 플로우 실행 (`run_flow.sh`)

---

## 3. 토큰 관련

```bash
make tokens
```

내부 실행:

```bash
source scripts/dev_tokens.sh
source scripts/load_tokens.sh
```

토큰 만료 시 다시 실행

---

## 4. 플로우 실행

```bash
make flow
```

---

## 5. Docker (개발/배포)

### 개발용

```bash
make docker-dev-build
make docker-dev-run
```

### 배포용

```bash
make docker-prod-build
make docker-prod-run
```

---

## 6. DB 마이그레이션 (Alembic)

```bash
make mig-new M="message"
make mig-up
make mig-current
make mig-heads
```

---

## 7. CI 강제 실행

```bash
make ci-trigger
```

---

## 8. 문자열 검색

```bash
make grep Q="검색어"
```

---

## 9. Supabase access_token 발급

```bash
make supabase-token
```

---

## 10. AWS / Copilot 도구

```bash
make aws-tools
make aws-check
```
---

# 운영 알람 / 롤백 런북

## A) CloudWatch 알람(이메일) 구성

### A-1. SNS 토픽/구독 정보
- SNS Topic Name: `crm-prod-alarms`
- SNS Topic ARN: `<TOPIC_ARN>`
- 이메일 구독: `<ALERT_EMAIL>`

> 변경/추가 가능:
> - 이메일 변경: 기존 구독 unsubscribe 후 새 이메일 subscribe
> - 동시에 여러 이메일/채널 구독 가능
> - SMS 등 다른 프로토콜도 추가 가능(추후)

### A-2. ALB / TargetGroup Dimension 값(고정해두기)
CloudWatch 메트릭은 아래 suffix 값이 필요함.
- PROD_LB_SUFFIX = `app/<lb-name>/<lb-id>`
- PROD_TG_SUFFIX = `<tg-name>/<tg-id>`

- STG_LB_SUFFIX = `app/<lb-name>/<lb-id>`
- STG_TG_SUFFIX = `<tg-name>/<tg-id>`

#### suffix 추출(태그 기반 리소스 찾기)
```bash
APP="crm"
ENV="prod"
SVC="api"

aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=copilot-application,Values=$APP" "Key=copilot-environment,Values=$ENV" "Key=copilot-service,Values=$SVC" \
  --resource-type-filters "elasticloadbalancing:loadbalancer" "elasticloadbalancing:targetgroup"
