# Codespace → 로컬 이전 안내 (2026-10-25)

> Codespace 를 그만 쓰고 로컬 PC 로 옮길 때 읽는 문서. 새 Claude Code 세션은 `CLAUDE.md` → `docs/progress.md` → 이 문서 순서로 읽으면 된다.

## 1. 지금 상태 한 줄 요약

- 백엔드 재구성·결함 수정·앱/웹 정리·성능 개선·데모 배포까지 끝났다. **하다 만 작업은 없다**
- 남은 일은 **결정이 필요한 것**과 **출시 준비**뿐: [launch-readiness.md](launch-readiness.md) (A 출시 전 할 일, B 개선할 문제, C 결정 필요, D 바로 할 수 있는 것)
- 진행 기록·타임라인·결정 이유: [progress.md](progress.md) (§3 타임라인, §7 결정 기록, §8 주의할 것)

## 2. 직접 옮겨야 하는 것

| 옮길 것 | 위치 | 방법 |
|---|---|---|
| **env 파일 5개** | `backend/.env`, `frontend/.env.local`, `apps/customer/.env`, `apps/instructor/.env`, `apps/.env`(ngrok) | git 에 없음. 각 폴더 `.env.example` 을 복사해 값을 다시 입력 ([operations/env-setup.md](operations/env-setup.md)). 값은 Supabase·AWS 대시보드·비밀번호 관리자에서 |
| **Claude 메모리** | 이 저장소의 `docs/claude-memory/` (Codespace 의 `~/.claude/projects/-workspaces-CRM-Core/memory/` 를 복사해 둔 것) | 아래 4절 |
| 로그인 | GitHub, AWS CLI, Expo | `gh auth login`(또는 git 자격 증명), `aws configure`, `eas login`. Codespace 는 GitHub 토큰을 자동으로 넣어 줬지만 로컬은 직접 |
| 편집기 설정 | `.vscode/settings.json` (git 제외) | Python 인터프리터를 `backend/.venv` 로 (`Python: Select Interpreter`) |

**옮길 필요 없는 것**: `node_modules`·`.venv`(다시 설치), 로컬 Docker DB(테스트용, `make apitest` 가 새로 만듦), 개발·데모 DB(클라우드), 화면 점검 도구(저장소 `tools/ui-check/` 로 옮겨 둠)

## 3. 로컬 준비

필요한 프로그램: **Git, Docker, Python 3.11 + Poetry, Node 24, make**

```bash
git clone https://github.com/DDukbagy/CRM_Core.git && cd CRM_Core
git checkout crm          # 작업 브랜치 (staging 에 아직 안 들어간 문서 커밋이 있을 수 있음)
git pull

cd backend && poetry install && cd ..
(cd frontend && npm ci); (cd apps/customer && npm ci); (cd apps/instructor && npm ci)

# env 파일 5개 작성 (2절) 후
make check      # 외부 서비스 없이 전체 검증 (Docker 필요)
make dbcheck    # 개발 DB 연결 확인 — Supabase 개발 프로젝트가 일시 중지면 대시보드에서 Restore
make api        # 백엔드
make web / make cweb / make iweb
```

- Windows 라면 WSL2 를 권장 (Makefile·쉘 스크립트가 bash 기준)
- `make iweb`·`make cweb` 첫 실행 때 Expo 버전 확인 네트워크 오류가 나면 다시 실행하거나 `EXPO_NO_DEPENDENCY_VALIDATION=1 make iweb`

## 4. Claude 메모리 옮기기

Claude Code 는 프로젝트 경로별로 메모리를 따로 저장한다. 로컬 경로가 바뀌므로 복사해 넣어야 이어서 기억한다.

1. 로컬에서 이 저장소 폴더로 Claude Code 를 한 번 실행한다 (메모리 폴더가 생김)
2. `~/.claude/projects/` 아래에 새로 생긴 폴더(로컬 경로를 `-` 로 이은 이름, 예: `-Users-나-CRM_Core`) 를 찾는다
3. 그 안의 `memory/` 에 `docs/claude-memory/*.md` 를 복사한다

```bash
mkdir -p ~/.claude/projects/<로컬경로-폴더>/memory
cp docs/claude-memory/*.md ~/.claude/projects/<로컬경로-폴더>/memory/
```

메모리 요약 (파일이 없어도 이 규칙은 지킨다):

| 메모리 | 내용 |
|---|---|
| keep-existing-features | 기능·준비 중 페이지·버튼을 지우지 않는다. UI·기능을 임의로 바꾸지 않는다. 완전히 죽은 코드만 삭제. git 이력에 있던 기능은 복원 대상 |
| no-commit-unless-asked | 사용자가 요청할 때만 커밋·push·PR. **커밋할지 묻지도 않는다** |
| no-repeat-status-reminders | 대기 중인 상태(예: "아직 merge 안 함")를 매 답변마다 반복하지 않는다 |
| makefile-target-naming | Makefile 타깃은 `<대상><동작>` (예: `apitest`, `iweb`) |
| dev-db-is-supabase | 개발 DB = 원격 Supabase(실데이터). 테스트는 로컬 컨테이너. 원격 마이그레이션은 승인 후에만 |
| demo-vs-production-deploy | 데모 = Render + Vercel 3개 + 데모 전용 Supabase (포트폴리오용 임시). 정식 출시 = AWS Copilot |

## 5. 작업할 때 기억할 것 (이번 대화에서 정한 것)

- **작업 방식**: 코드 수정 전 영향 범위 보고 → 승인 → 진행 (CLAUDE.md §0). 답을 먼저 하고 진행하라는 요청이 많음
- **브랜치**: `crm` 에서 작업 → `staging` 대상 PR → CI 확인 → squash merge. merge 후 GitHub 봇이 `crm` 에 병합 커밋을 push 하므로 다음 작업 전 `git pull`(또는 rebase). `main` 은 정식 배포 때 Release PR 로만
- **데모**: staging 을 따라 자동 배포. 마이그레이션·새 환경변수는 데모에 **직접** 반영 ([progress.md](progress.md) §6-2, [operations/demo-deploy.md](operations/demo-deploy.md)). Vercel 세 프로젝트의 Branch Tracking 은 모두 `staging`
- **비밀값**: env 파일은 읽지도 출력하지도 않는다 (CLAUDE.md §4). 데모 값은 Render·Vercel 대시보드에만
- **블로그(티스토리 개발일지)**: 작업 단위로 묶어 7편 구성 추천 — 0 개요(타임라인) · 1 백엔드 구조 · 2 거래 데이터 결함 · 3 화면 점검·기능 정리 · 4 커넥션 풀 성능 · 5 자정 프로모션(한국 날짜) · 6 데모 배포에서만 드러난 버그 · 7 출시까지 남은 것. 자료: `progress.md` §3·§7, `docs/portfolio/`, PR #73~#77
- **먼저 정할 것** (출시 필수와 연결): 회원가입 방식, 강사 승인 운영 방식 ([launch-readiness.md](launch-readiness.md) C)

## 6. 저장소 안의 주요 문서

| 문서 | 내용 |
|---|---|
| `CLAUDE.md` | 규칙 (모든 세션이 먼저 읽음) |
| `docs/progress.md` | 상태·타임라인·결정 기록·주의할 것 |
| `docs/launch-readiness.md` | 출시 전 할 일·AWS 설정·개선할 문제·결정 필요 항목 |
| `docs/operations/` | env 설정, 로컬 명령, 검증 절차, 데모 배포, AWS, PG 연동, 문제 해결 |
| `docs/portfolio/` | 문제 해결 기록 (커넥션 풀 성능) |
| `docs/claude-memory/` | Claude 메모리 사본 |
| `tools/ui-check/` | 화면 점검 도구 (Playwright) |
