# Troubleshooting

자주 발생하는 문제와 해결 방법을 정리합니다.

---

## 1. 토큰 발급 실패 (401 / Bad hostname)

**원인**

* `SUPABASE_URL` placeholder 미수정
* Windows CRLF (`^M`) 포함

**해결**

```bash
sed -i 's/\r$//' .env scripts/*.sh
```

---

## 2. 인터프리터가 시스템 Python으로 잡힘

**해결**

```bash
poetry env info -p
which python
python -c "import sys; print(sys.prefix)"
```

* `.venv` 경로면 정상

---

## 3. rebuild 후 파일이 사라짐

**원인**

* `/workspace`에서 작업

**해결**

* `/workspaces/<repo>` 에서 작업

---

## 4. Git dubious ownership 에러

```bash
git config --global --add safe.directory /workspaces/CRM_Core
```

---

## 5. aws / copilot command not found

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## 6. 포트 충돌

```bash
make dockps
make dockstop ID=<container>
```

---

## 7. `curl` 결과가 `[000]`

백엔드에 연결이 안 된 것. `make api` 터미널이 꺼졌거나 오류로 멈춘 상태 → 다시 `make api`, `curl http://127.0.0.1:8000/health` 가 200 인지 확인.

---

## 8. 앱에서 요청이 404, 백엔드 로그에 `path=//users/me`

`EXPO_PUBLIC_API_BASE_URL` 끝에 `/` 가 붙은 경우. 2026-10-02 부터 앱이 자동으로 떼지만, 값도 `/` 없이 두는 게 좋다.

---

## 9. 앱이 내 `.env` 와 다른 주소로 요청함

Expo 는 `.env.local` 을 `.env` 보다 우선한다. 각 앱 폴더에 남은 `.env.local` 이 있는지 확인하고 지운다. 그다음 `make cweb`·`make iweb` 을 다시 실행한다. 화면 점검 도구가 만드는 임시 `.env.local` 은 점검이 끝나면 지워진다.

---

## 10. 브라우저로 연 앱에서 확인창이 필요한 버튼이 반응 없음

`react-native` 의 `Alert.alert` 는 웹에서 아무것도 띄우지 않는다. 확인창·알림은 반드시 각 앱의 `lib/alert.ts` 에 있는 `appAlert` 로 띄운다. 폰에서는 `Alert.alert`, 웹에서는 브라우저 확인창을 쓴다.

---

## 11. 빈 DB 에 `alembic upgrade head` 가 `DuplicateTable`·`DuplicateColumn`·`NoReferencedTableError` 로 실패

init 마이그레이션(`91d68413f8d6`)이 *현재* 모델로 `create_all` 하기 때문. 새 컬럼은 `ADD COLUMN IF NOT EXISTS`, 나중에 만들어지는 테이블을 참조하는 모델은 `app/db/models.py` 에 등록하지 않고 `alembic/env.py` 의 비교 명령 분기에서 올린다(progress.md §8). 공유된 revision 은 고치지 않는다.

---

## 12. Expo 가 코드를 고쳐도 옛 화면을 보여 줌

파일 감시가 변경을 놓친 경우. 서버를 끄고 `npx expo start --web --clear` 로 다시 띄운다.

---

## 13. Shift+Enter 가 줄바꿈 대신 전송됨 (Claude Code, Codespaces)

`/terminal-setup` 은 컨테이너 안 설정만 바꾼다. 키 입력을 받는 건 **내 PC 쪽 VS Code** 라서, 거기 Keyboard Shortcuts (JSON) 에 직접 추가한다.

```json
{ "key": "shift+enter", "command": "workbench.action.terminal.sendSequence", "args": { "text": "\u001b\r" }, "when": "terminalFocus" }
```

