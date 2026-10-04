# Dev Runbook (개발 명령어 모음)

이 문서는 **개발/운영 중 자주 쓰는 명령어를 정리한 실행 가이드**입니다. 모든 명령은 저장소 루트에서 실행합니다.
전체 목록은 `make help` 로 볼 수 있습니다.

## 타깃 이름 규칙

`<대상><동작>`, 소문자 붙여쓰기. 예) `iweb` = 강사 앱(i)을 웹(web)으로 실행

| 대상 | 뜻 | 대상 | 뜻 |
|---|---|---|---|
| `api` | 백엔드 | `db` | 데이터베이스 |
| `web` | 관리자·강사 웹 | `mig` | 마이그레이션 |
| `c` | 고객 앱 | `dock` | Docker |
| `i` | 강사 앱 | `git` | 브랜치·배포 |
| `aws` | AWS 도구 | `stg` / `prod` | Copilot 환경 |

예외: `help`, `check`(전체 검증), `grep`

---

## 1. 실행

```bash
make api        # 백엔드 개발 서버 (backend/.env 사용, reload)
make web        # 관리자·강사 웹 (Next.js)
make cweb       # 고객 앱 (브라우저)
make ctunnel    # 고객 앱 (실기기, QR)
make iweb       # 강사 앱 (브라우저, 8082)
make itunnel    # 강사 앱 (실기기, QR)
```

## 2. 검사·테스트 (로컬 DB, 원격 연결 없음)

PR 전에는 `make check` 를 통과시킵니다.

```bash
make check      # 아래 4개 전부
make apitest    # 백엔드: 로컬 DB 새로 만들기 → alembic check → pytest
make webcheck   # 웹: lint + 타입 검사
make ccheck     # 고객 앱 타입 검사
make icheck     # 강사 앱 타입 검사

make apitest ARGS="-k calendar"   # 일부 테스트만
```

* 로컬 DB는 Docker 컨테이너 `crm-local-db`(127.0.0.1:55433)로 자동 실행됩니다.
* 로컬 검증 설정은 `backend/scripts/local_env.sh`(더미 값)이며 `backend/.env` 는 쓰지 않습니다.

### 원클릭 로컬 검증

```bash
make apiverify
```

* 동작: 로컬 DB(`crm_verify`) 준비 → 서버 실행 → 관리자·강사·고객 토큰 발급(로컬 더미 서명) → 강사 승인 → `run_flow.sh`(캘린더·슬롯·예약·철회 14단계) → 서버 종료

## 3. 실행 중인 서버 점검 (실제 Supabase)

* 실제 Supabase 로그인·S3 검증 절차는 [verification.md](verification.md) 참고

```bash
make apitoken   # 실제 Supabase 계정으로 access token 발급 (대화형)
make apiflow    # BASE_URL, HOST_TOKEN, GUEST_TOKEN, HOST_ID 를 export 한 뒤 주요 흐름 실행
make apismoke   # 예약 스모크 테스트 (API_URL, SUPABASE_URL, SUPABASE_ANON_KEY 필요)
```

## 4. 데이터베이스

```bash
make dbup       # 로컬 Postgres 컨테이너 시작
make dbdown     # 로컬 Postgres 컨테이너 중지
make dbcheck    # backend/.env 의 DB 연결 확인
make dbschema   # 모델 테이블·컬럼과 DB 비교
make dbreset    # 로컬 DB만 초기화 (호스트가 localhost 가 아니면 거부, DB 이름 입력 확인)
```

* 개발 데이터: `backend/scripts/seed_dev_data.sql` 을 psql 로 실행

## 5. 마이그레이션 (backend/.env 의 DB 대상)

```bash
make mignew M="message"   # 새 리비전 (autogenerate 결과는 한 줄씩 검토)
make migup                # head 까지 적용
make migcur               # 현재 리비전
make migheads             # head 목록
make migcheck             # 모델 ↔ DB 불일치 확인 (읽기 전용)
```

* 원격 DB(Supabase)에 `migup` 은 승인 후에만 실행합니다 (CLAUDE.md §9).

## 6. Docker (backend/Dockerfile)

```bash
make dockbuild                  # 이미지 빌드 (IMAGE=crm-backend)
make dockrun                    # 이미지 실행 (:8000 → 8080, backend/.env)
make dockdev                    # ./backend 를 마운트하고 자동 reload
make dockps                     # 'crm-backend' 이름이 포함된 컨테이너 조회
make dockstop ID=<container>    # 특정 컨테이너 정지
```

## 7. Git · 배포

```bash
make gitbranch        # staging 최신화 → 브랜치 삭제(로컬+원격) → 새 브랜치 생성 (대화형)
make gitci            # 빈 커밋으로 CI 실행
make gitpr            # staging → main Release PR 생성
make gitrelease       # 최신 main 에 버전 태그(vX.Y.Z) 생성·push → 원래 브랜치 복귀
make gitrollbackdry   # 태그로 롤백할 때 바뀌는 파일 미리보기 (변경 없음)
make gitrollback      # [위험] main 을 태그 내용으로 되돌리는 새 커밋 → push (배포 실행)
```

* 배포는 태그가 아니라 **main push** 로 실행됩니다. `gitrelease` 의 태그는 롤백 기준점입니다.

## 8. 문자열 검색

```bash
make grep Q="검색어"   # .venv·.git·node_modules, env·pem·key 파일 제외
```

## 9. AWS · Copilot

```bash
make awsinstall   # AWS CLI / Copilot 설치
make awscheck     # 버전 확인
make awswho       # 현재 AWS 계정 확인
make awsenvs      # Copilot 환경 목록

make stgstatus    # staging 서비스 상태
make stglogs      # staging 로그 (follow)
make stgexec      # staging 컨테이너 접속
make stgdeploy    # staging 수동 배포
make stgalarm     # staging ALB/TG suffix (CloudWatch)

make prodstatus
make prodlogs
make proddeploy   # 주의: 수동 prod 배포
make prodalarm
```
