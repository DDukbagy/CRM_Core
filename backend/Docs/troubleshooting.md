# Troubleshooting

자주 발생하는 문제와 해결 방법을 정리합니다.

---

## 1. 서버는 켜져 있는데 verify가 실패함

**증상**

* 포트는 열려 있는데 health 체크 실패

**해결**

* 실제 health 엔드포인트 확인 (`/health_db`, `/openapi.json` 등)
* `verify.sh`의 `HEALTH_PATHS_DEFAULT` 수정

---

## 2. 토큰 발급 실패 (401 / Bad hostname)

**원인**

* `SUPABASE_URL` placeholder 미수정
* Windows CRLF (`^M`) 포함

**해결**

```bash
sed -i 's/\r$//' .env scripts/*.sh
```

---

## 3. 인터프리터가 시스템 Python으로 잡힘

**해결**

```bash
poetry env info -p
which python
python -c "import sys; print(sys.prefix)"
```

* `.venv` 경로면 정상

---

## 4. rebuild 후 파일이 사라짐

**원인**

* `/workspace`에서 작업

**해결**

* `/workspaces/<repo>` 에서 작업

---

## 5. Git dubious ownership 에러

```bash
git config --global --add safe.directory /workspaces/crm_backend
```

---

## 6. aws / copilot command not found

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## 7. 포트 충돌

```bash
make docker-ps
make docker-stop ID=<container>
```
