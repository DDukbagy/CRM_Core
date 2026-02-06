# crm_backend

## Quick Start

```bash
# 최초 1회
authmod +x scripts/verify.sh
make verify
```

* 서버가 꺼져 있으면 자동 실행
* 토큰 발급 → 플로우 실행까지 원클릭

## Common Commands

```bash
make server         # 개발 서버 실행
make verify         # 원클릭 검증
make tokens         # 테스트 토큰 발급
make flow           # 플로우 실행
make test           # 테스트 실행
make release        # release 배포 실행
make rollback       # rollback 실행
make rollback-dry   # dry rollback 실행
make branch-reset   # branch 리셋
```

---

# 운영 & 배포 가이드 

## 🚀 배포 프로세스 (Deployment Pipeline)

**"Code Push → Test → Staging Deploy → Main Merge → Prod Deploy"**

### 1️⃣ 개발 단계 (Development)
1. **작업 브랜치 생성**
   - `make branch-reset` 명령어로 Staging 동기화 및 브랜치 생성
2. **코드 작성 및 푸시**
   - 작업 후 `git commit` → `git push`
3. **PR 생성 및 테스트**
   - GitHub에서 PR 생성 (`feature` → `staging`)
   - **CI (Test)** 자동 실행

### 2️⃣ 스테이징 배포 (Staging)
4. **Staging 병합 (Merge)**
   - CI 통과 시 `staging` 브랜치로 Merge
5. **자동 배포 (Deploy Staging)**
   - Merge 즉시 **CI** 재실행 → 성공 시 **Deploy Staging** 워크플로우 실행
   - 배포 성공 시 **"Release: Staging to Main"** PR 자동 생성

### 3️⃣ 운영 배포 (Production)
6. **Main 병합 (Merge to Main)**
   - 자동 생성된 PR 확인 후 **Merge** 버튼 클릭
7. **자동 배포 (Deploy Prod)**
   - Main Merge 즉시 **CI** 재실행 → 성공 시 **Deploy Prod** 워크플로우 실행
8. **배포 완료**
   - 🚀 Production 환경 배포 완료

---

## 운영 환경 구성

* dev: 로컬 / Codespace 개발
* staging: AWS 리허설 환경
* prod: 실제 운영 환경

---

## 중요한 운영 원칙

* CI 실패 상태에서는 절대 merge하지 않는다
* staging 확인 없이 prod 배포하지 않는다
* prod 배포는 항상 승인 단계를 거친다

---

## 수동 배포가 필요한 경우

자동 배포가 실패했거나, 긴급 복구가 필요한 경우:

```bash
make copilot-deploy-staging
make copilot-deploy-prod
```

---

## 로그 확인

```bash
make copilot-logs-staging
make copilot-logs-prod
```

---

## 장애 대응 기본 체크리스트

* CI 상태 확인
* staging 상태 확인
* 로그 확인
* 환경변수/시크릿 확인

---

## 문서 참고

* aws.md: AWS / Copilot 운영 상세 가이드


자세한 내용은 아래 문서를 참고하세요.

* 개발 명령어 모음: `docs/dev-runbook.md`
* 문제 해결 모음: `docs/troubleshooting.md`
