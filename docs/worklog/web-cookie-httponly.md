# 웹 로그인 쿠키 HttpOnly

- 상태: 완료
- 기간: 2026-11-15 ~ 2026-11-17
- 브랜치 / PR: `crm`
- 관련 작업: [HS256 폴백 평소 끄기](hs256-fallback-off.md)

## 1. 문제

웹(관리자·강사)의 로그인 세션 쿠키(`sb-<프로젝트>-auth-token`, access token·refresh token)를 브라우저 JS 가 읽을 수 있다.

- 로그인을 브라우저에서 한다 (`frontend/src/app/login/page.tsx` 의 `supabaseBrowser().auth.signInWithPassword`). 세션 쿠키는 브라우저 JS 가 `document.cookie` 로 쓰므로 HttpOnly 를 붙일 수 없다. 로그아웃도 브라우저에서 한다 (`DashboardLayout.tsx`, `forbidden/page.tsx`).
- 쿠키 옵션은 `@supabase/ssr` 기본값 그대로다: `httpOnly: false`, `sameSite: lax`, `maxAge` 400일, `secure` 지정 없음.
- 웹에 XSS 가 하나라도 생기면 스크립트가 access token 과 refresh token 을 그대로 읽어 갈 수 있다. refresh token 이 있으면 계속 새 토큰을 받을 수 있어 계정을 오래 빼앗긴다.
- 웹은 이미 모든 API 를 Next 서버의 `/api/[...path]` 프록시로 보내고, 프록시가 쿠키에서 토큰을 꺼내 백엔드에 Bearer 로 붙인다. 브라우저가 토큰을 직접 알아야 할 이유가 없다.

함께 발견한 것: 어디서도 쓰지 않는 인증 관련 파일이 3개 있다 (`app/login/actions.ts` 서버 액션 로그인, `app/api/auth/sync/route.ts`, `lib/providers.tsx`). `providers.tsx` 는 일반 `createClient` 를 써서, 쓰였다면 세션을 localStorage 에 저장했을 코드다.

## 2. 테스트 명세

- [ ] 로그인하면 → 세션 쿠키에 `HttpOnly` 와 `SameSite=Lax` 가 붙어야 한다
- [ ] 로그인하면 → 페이지의 JS 로는 `document.cookie` 에서 세션 쿠키를 볼 수 없어야 한다
- [ ] 로그인하면 → API(`/api/users/me`)는 정상(200)이어야 한다
- [ ] 로그아웃하면 → 세션 쿠키가 만료되어야 한다
- [ ] 로그아웃한 뒤 로그인이 필요한 화면에 들어가면 → 로그인 화면으로 보내져야 한다

## 3. 재현 (고치기 전)

- 테스트 이름 또는 실행한 명령: `E2E_EMAIL=… E2E_PASSWORD=… make webe2e` (`frontend/e2e/session-cookie.spec.ts` 5개, 명세 1~5 에 하나씩)
- 실행 환경: 로컬 웹(`make web`, `localhost:3000`) + 로컬 백엔드(`make api`) + 개발 Supabase Auth, Playwright 1.64.1 Chromium. 개발 Supabase 의 강사 테스트 계정
- 커밋: `2477183` (수정 전) + 테스트 파일
- 결과: 명세 1·2 가 실패했다. 명세 3·4·5 는 지금도 맞는 동작이라 통과한다 (고친 뒤에도 깨지지 않아야 하는 동작). 쿠키 값(토큰)은 기록에서 지웠다.

```text
  ✘  1 … 명세 1: 로그인하면 세션 쿠키에 HttpOnly·SameSite=Lax 가 붙는다 (6.5s)
  ✘  2 … 명세 2: 로그인해도 document.cookie 에 세션 쿠키가 없다 (1.0s)
  ✓  3 … 명세 3: 로그인하면 /api/users/me 가 200 이다 (1.1s)
  ✓  4 … 명세 4: 로그아웃하면 세션 쿠키가 사라진다 (1.1s)
  ✓  5 … 명세 5: 로그아웃 뒤 보호 화면에 들어가면 로그인 화면으로 간다 (1.3s)

  1) 명세 1
    Error: sb-<프로젝트>-auth-token
    expect(received).toBe(expected) // Object.is equality
    Expected: true
    Received: false
    > 48 |     expect(c.httpOnly, c.name).toBe(true);

  2) 명세 2
    Error: expect(received).not.toMatch(expected)
    Expected pattern: not /-auth-token(\.\d+)?=/
    Received string:      "sb-<프로젝트>-auth-token=base64-eyJhY2Nlc3NfdG9rZW4i…(토큰, 생략)"
    > 61 |   expect(visible).not.toMatch(/-auth-token(\.\d+)?=/);

  2 failed
  3 passed (12.9s)
```

| 명세 | 기대 | 실제 (고치기 전) | 뜻 |
|---|---|---|---|
| 1. 세션 쿠키 HttpOnly·SameSite | `httpOnly: true`, `Lax` | `httpOnly: false` | 브라우저 JS 가 쓴 쿠키라 HttpOnly 가 없음 |
| 2. `document.cookie` 에 세션 쿠키 없음 | 없음 | 있음 (access token·refresh token 이 담긴 값 전체) | 페이지의 JS 가 토큰을 그대로 읽을 수 있음 |
| 3. `/api/users/me` | 200 | 200 | 통과 (유지해야 할 동작) |
| 4. 로그아웃 후 세션 쿠키 | 없음 | 없음 | 통과 (지금은 JS 가 지움. 고친 뒤에는 서버가 지워야 함) |
| 5. 로그아웃 후 보호 화면 | 로그인 화면 | 로그인 화면 | 통과 (유지해야 할 동작) |

준비 중 겪은 것: 처음에는 5개 모두 로그인 단계에서 시간 초과로 실패했다. 로컬 웹의 `API_BASE_URL` 이 로컬 백엔드가 아닌 다른 서버의 `http://` 주소여서 프록시가 308 리다이렉트를 받았고, 로그인 화면이 역할을 읽지 못해 로그아웃시켰다. 문서(`docs/operations/env-setup.md`)대로 `http://localhost:8000` 으로 맞춘 뒤 위 결과가 나왔다.

## 4. 원인

HttpOnly 쿠키는 서버의 `Set-Cookie` 로만 만들 수 있다. 그런데 세션 쿠키를 만드는 주체가 브라우저 JS 였다.

- `frontend/src/app/login/page.tsx`: `supabaseBrowser()`(`@supabase/ssr` 의 `createBrowserClient`)로 `signInWithPassword` 를 부른다. 브라우저 클라이언트는 받은 세션을 `document.cookie` 로 쓴다. JS 가 쓰는 쿠키에는 HttpOnly 를 붙일 수 없고, 붙이면 브라우저 클라이언트가 세션을 읽지 못한다.
- 로그아웃도 브라우저에서 `signOut` 으로 쿠키를 지웠다 (`DashboardLayout.tsx`, `forbidden/page.tsx`).
- 서버 쪽 Supabase 클라이언트(`lib/supabase/server.ts`, `proxy.ts`, `/api/[...path]`)도 쿠키 옵션을 지정하지 않아 `@supabase/ssr` 기본값(`httpOnly: false`, `maxAge` 400일)을 썼다.
- 반면 실제로 토큰이 필요한 곳은 모두 서버였다: `proxy.ts` 가 보호 화면에서 로그인을 확인하고, `/api/[...path]` 가 쿠키의 토큰을 Bearer 로 백엔드에 붙인다. 브라우저 JS 가 토큰을 들고 있을 이유가 없었다.
- 서버 로그인 코드(`app/login/actions.ts`)는 이미 있었지만 어디서도 쓰지 않았다.

## 5. 선택지와 결정

| 선택지 | 방식 | 장점 | 단점 |
|---|---|---|---|
| A. 서버 로그인 + HttpOnly | 로그인·로그아웃을 Next 서버(서버 액션·라우트)로 옮기고, 서버 Supabase 클라이언트에 `httpOnly: true`, `secure`(운영), `sameSite: lax` 를 지정한다. 브라우저는 세션을 직접 다루지 않는다. API 프록시도 갱신된 쿠키를 응답에 저장한다 | XSS 가 생겨도 토큰을 읽어 갈 수 없다. 이미 프록시 구조라 브라우저가 토큰을 알 필요가 없다. 쓰지 않던 서버 액션 로그인을 되살려 쓸 수 있다 | 로그인·로그아웃 흐름이 바뀐다. 웹 파일 6~8개 수정. 백엔드 테스트로는 확인할 수 없어 브라우저로 확인해야 한다 |
| B. 그대로 두고 완화 | `secure` 지정, 쿠키 유지 기간 단축, CSP(실행할 수 있는 스크립트 제한) 추가 | 변경이 작다 | 토큰을 JS 로 읽을 수 있다는 근본 문제는 그대로 |
| C. 고칠 필요 없음 | 위험과 이유를 기록만 한다 | 변경 없음 | XSS 가 생겼을 때 피해가 그대로 크다 |
| (참고) 백엔드가 쿠키 발급 | FastAPI 가 로그인 응답에 쿠키를 준다 | 쿠키를 한 곳에서 관리 | 백엔드와 웹의 도메인이 달라 쿠키 설정이 복잡하다. 웹은 프록시로 Bearer 만 넘기고 두 앱도 Bearer 를 쓰는 지금 구조와 맞지 않는다 |

- 고른 것: A. 서버 로그인 + HttpOnly
- 이유: 보안 강화를 위해서다.

## 6. 수정

- 바꾼 파일 (모두 `frontend/src`):
  - `lib/supabase/cookies.ts` (새 파일): 세션 쿠키 옵션 `httpOnly: true`, `sameSite: "lax"`, `secure`(운영에서만, 로컬 http 에서는 붙이면 저장되지 않음)를 한 곳에 정의
  - `lib/supabase/server.ts`, `proxy.ts`: Supabase 서버 클라이언트에 이 쿠키 옵션 적용
  - `app/login/actions.ts`: 쓰지 않던 서버 액션 로그인을 되살렸다. 로그인 → 백엔드 `/users/me` 로 역할 확인(서버에서 서버로, 최초 로그인 시 JIT 사용자 생성도 이때) → 역할별 화면으로 이동. 역할을 못 읽거나 일반 회원이면 서버에서 로그아웃하고 지금과 같은 안내 문구로 로그인 화면에 돌려보낸다. `logoutAction` 추가 (서버가 세션 쿠키를 지움)
  - `app/login/page.tsx`: 폼이 서버 액션을 부른다. 입력칸 이름·화면·문구는 그대로. "이미 로그인돼 있으면 이동"은 브라우저 Supabase 대신 `/api/users/me` 로 확인
  - `app/login/redirect.ts` (새 파일): `sanitizeNext`·`pickRedirectPath` 를 로그인 화면에서 꺼내 서버 액션과 같이 쓴다 (동작 그대로)
  - `app/api/[...path]/route.ts`: access token 이 만료돼 Supabase 가 갱신하면, 갱신된 쿠키를 응답에 다시 저장한다 (전에는 `setAll` 이 비어 있어 저장하지 않았다)
  - `components/layout/DashboardLayout.tsx`, `app/forbidden/page.tsx`: 로그아웃 버튼이 `logoutAction` 을 부른다
  - 삭제: `lib/supabase/client.ts`(브라우저 Supabase 클라이언트, 더 이상 쓰는 곳 없음), `lib/providers.tsx`·`app/api/auth/sync/route.ts`(원래 쓰지 않던 파일)
  - 테스트: `frontend/e2e/session-cookie.spec.ts`, `frontend/playwright.config.ts`, `@playwright/test` 1.64.1(devDependency), `make webe2e`, `frontend/.gitignore` 에 테스트 결과 폴더
- 영향 범위 (API 계약, DB, 웹·앱):
  - API 계약·DB: 변경 없음
  - 백엔드·두 모바일 앱: 변경 없음 (앱은 쿠키가 아니라 Bearer 를 쓴다)
  - 웹: 로그인·로그아웃이 서버 액션으로 바뀜. 화면과 문구는 같다
  - CI: 브라우저 테스트는 실제 Supabase 로그인이 필요해 CI 에서 돌리지 않는다 (`make webe2e` 로 로컬 실행)
- 커밋 / PR: `crm` 브랜치 한 커밋 (테스트·수정·문서)

## 7. 결과 (고친 후)

- 같은 테스트의 실행 결과: 같은 환경(로컬 웹·백엔드 + 개발 Supabase, 강사 테스트 계정)에서 `make webe2e` 5개 모두 통과
- `make webcheck`(웹 lint + 타입 검사) 통과

| 항목 | 전 | 후 | 측정 조건 |
|---|---|---|---|
| 명세 1~5 브라우저 테스트 | 2 failed, 3 passed | 5 passed | 로컬 웹·백엔드, 개발 Supabase, Playwright Chromium |
| 세션 쿠키 `httpOnly` | false | true | 같음 |
| 세션 쿠키 `Secure` | 없음 | 있음 | 데모 웹(Vercel, HTTPS) |
| `document.cookie` 의 세션 쿠키 | 보임 (토큰 전체) | 안 보임 | 같음 |

## 8. 남은 것

- `secure` 는 운영(HTTPS)에서만 붙어 로컬 테스트로는 확인할 수 없었다. merge 후 데모 웹(Vercel)에서 로그인해 확인했다: 세션 쿠키 `Set-Cookie: …; Path=/; Secure; HttpOnly; SameSite=lax`
- 세션 쿠키 유지 기간은 `@supabase/ssr` 기본값(400일)을 그대로 쓴다. 쿠키 안의 refresh token 은 Supabase 가 따로 만료·회전하지만, 쿠키 기간을 줄일지는 나중에 본다
- XSS 자체를 막은 것은 아니다. HttpOnly 는 XSS 가 생겼을 때 토큰을 밖으로 가져가지 못하게 할 뿐, 페이지가 열려 있는 동안 그 사용자로 요청을 보내는 것은 막지 못한다. CSP·게시물 미디어 주소 검사는 별도 작업
- 브라우저 테스트는 CI 에서 돌지 않는다. 실제 Supabase 계정이 필요하기 때문이다
- 테스트가 실패하면 Playwright 화면 기록(`frontend/test-results/`)에 입력한 계정 정보가 남는다. git 에서는 제외돼 있지만 확인 후 지운다
- 처음 실행 때 명세 2 의 실패 메시지가 `document.cookie` 를 통째로 출력해 토큰이 보였다. 쿠키 이름만 확인하도록 테스트를 바꿨다
- 보호 화면(`proxy.ts`)과 `/api` 프록시가 토큰을 갱신한다. 로그인 화면처럼 둘 다 거치지 않는 화면에 오래 머물면 갱신이 늦어질 수 있지만, 다음 API 요청 때 프록시가 갱신한다

## 9. 배운 것

처음 테스트를 돌렸을 때 실패 메시지가 `document.cookie` 를 그대로 출력해서 실제 토큰이 화면에 찍혔다. 브라우저 JS 가 세션을 직접 다루면 XSS 가 하나라도 생겼을 때 그 스크립트가 쿠키에서 토큰을 그대로 가져갈 수 있다는 보안 취약점과, HttpOnly 쿠키는 서버만 만들 수 있다는 것을 알게 되었다. 이를 막기 위해 로그인·로그아웃을 서버로 옮겨 HttpOnly 를 켜고, 테스트도 쿠키 이름만 확인하도록 바꿨다. 다만 이것으로 끝이 아니라, URL 형식 검사와 CSP 까지 해야 XSS 를 더 효과적으로 막을 수 있다는 것도 알았다.
