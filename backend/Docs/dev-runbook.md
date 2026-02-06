# Dev Runbook (개발 명령어 모음)

이 문서는 **개발/운영 중 자주 쓰는 명령어를 정리한 실행 가이드**입니다.

---

## 1. 서버 실행

```bash
make server
```

### 내부 명령:

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 2. 원클릭 검증 (추천)

```bash
make verify
```

* 동작 순서:
1. 서버가 켜져 있으면 그대로 사용
2. 꺼져 있으면 자동 실행
3. 토큰 발급 (`dev_tokens.sh`, `load_tokens.sh`)
4. 플로우 실행 (`run_flow.sh`)

---

## 3. 토큰 관련

```bash
make tokens
```

* 내부 실행:

```bash
source scripts/dev_tokens.sh
source scripts/load_tokens.sh
```

* 토큰 만료 시 다시 실행

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

## 11. 운영 알람 확인/복구
```bash
make alarms-prod-dim
make alarms-stg-dim     # rehearsal 알람은 선택
```

## 12. DB 연결 및 스키마 검증

* DB 연결 상태와 테이블/컬럼이 올바르게 생성되었는지 정밀 검사합니다.

```bash
make check-db      # DB 접속 테스트 (Ping)
make check-schema  # 테이블 및 필수 컬럼 생성 여부 검증
```

## 13. Docker 프로세스 관리

* 개발 중 실행된 컨테이너를 조회하거나 정리할 때 사용합니다.

```bash
make docker-ps                  # 'crm-backend' 이름이 포함된 컨테이너만 필터링 조회
make docker-stop ID=<container> # 특정 컨테이너 정지 (ID 또는 이름)
```

## 14. 배포 및 롤백 (Release & Rollback)

* Git 태그를 기반으로 운영(Prod) 배포와 롤백을 수행하는 대화형 명령어입니다.

### 정기 배포 (Release)

* main 브랜치 최신화 후 태그를 생성하여 배포를 트리거합니다.

```bash
make release
```
* 동작: main 전환 → Pull → 버전 태그 입력(예: v0.1.0) → Push → 원래 브랜치 복귀

### 롤백 (Rollback)

* 이전 버전의 태그를 가리키는 새로운 태그를 생성하여 재배포합니다.

```bash
make rollback-dry   # 롤백 시뮬레이션 (변경 없음, 태그 생성 안 함)
make rollback-safe  # 실제 롤백 실행 (대화형 확인 절차 포함)
```

## 15. Git 브랜치 초기화

* 작업 중인 로컬/원격 브랜치를 삭제하고 main 기반으로 다시 만들 때 사용합니다. (브랜치가 꼬였을 때 유용)

```bash
make branch-reset
```

## 16. Copilot 운영 단축어

* aws.md에 있는 긴 명령어들을 Makefile 단축어로 실행할 수 있습니다.

### Staging 환경
```bash
make copilot-status-staging  # 서비스 상태 확인
make copilot-logs-staging    # 실시간 로그 확인 (Follow)
make copilot-exec-staging    # 컨테이너 쉘 접속
make copilot-deploy-staging  # 수동 배포
```

### Prod 환경
```bash
make copilot-status-prod
make copilot-logs-prod
# make copilot-deploy-prod  <-- 주의: 가급적 'make release' 사용 권장
```

## 17. AWS 자격증명 확인

* 현재 로컬에 설정된 AWS 계정 정보를 확인합니다.

```bash
make aws-whoami
```