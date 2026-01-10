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
make server        # 개발 서버 실행
make verify        # 원클릭 검증
make tokens        # 테스트 토큰 발급
make flow          # 플로우 실행
make test          # 테스트 실행
```

자세한 내용은 아래 문서를 참고하세요.

* 개발 명령어 모음: `docs/dev-runbook.md`
* 문제 해결 모음: `docs/troubleshooting.md`
