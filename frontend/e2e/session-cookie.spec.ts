// 웹 로그인 세션 쿠키: HttpOnly, 로그인 후 API, 로그아웃
// 명세: docs/worklog/web-cookie-httponly.md 2절
//
// 웹으로 로그인할 수 있는 강사(또는 관리자) 계정이 필요하다. E2E_EMAIL, E2E_PASSWORD 로 넘긴다 (값은 저장소에 넣지 않는다).
// 세션 쿠키는 이름이 sb-<프로젝트>-auth-token 이고, 길면 .0 .1 로 나뉜다. 다른 sb- 쿠키는 확인 대상이 아니다.
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;

test.skip(!EMAIL || !PASSWORD, "E2E_EMAIL, E2E_PASSWORD 가 필요하다 (웹으로 로그인할 수 있는 강사 계정)");

const SESSION_COOKIE = /^sb-.+-auth-token(\.\d+)?$/;

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[name="username"]', EMAIL!);
  await page.fill('input[name="password"]', PASSWORD!);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(instructor|admin)(\/|$)/);
}

async function sessionCookies(context: BrowserContext) {
  return (await context.cookies()).filter((c) => SESSION_COOKIE.test(c.name));
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "로그아웃" }).click();
  await page.waitForURL(/\/login/);
}

// 명세 1: 로그인을 하면 → 세션 쿠키에 HttpOnly, SameSite=Lax
test("명세 1: 로그인하면 세션 쿠키에 HttpOnly·SameSite=Lax 가 붙는다", async ({ page, context }) => {
  await login(page);
  const cookies = await sessionCookies(context);
  expect(cookies.length, "세션 쿠키가 없다 (로그인 실패?)").toBeGreaterThan(0);

  for (const c of cookies) {
    expect(c.httpOnly, c.name).toBe(true);
    expect(c.sameSite, c.name).toBe("Lax");
  }
});

// 명세 2: 로그인을 하면 → 페이지의 JS(document.cookie)로 세션 쿠키를 볼 수 없다
test("명세 2: 로그인해도 document.cookie 에 세션 쿠키가 없다", async ({ page }) => {
  await login(page);
  const visible = await page.evaluate(() => document.cookie); // 페이지 안의 JS 가 보는 쿠키 문자열 ("a=1; b=2")
  // 실패할 때 토큰 값이 출력되지 않도록 쿠키 이름만 뽑아서 확인한다
  const visibleNames = visible.split("; ").map((kv) => kv.split("=")[0]);

  expect(visibleNames.filter((name) => SESSION_COOKIE.test(name))).toEqual([]);
});

// 명세 3: 로그인을 하면 → /api/users/me 는 200
test("명세 3: 로그인하면 /api/users/me 가 200 이다", async ({ page }) => {
  await login(page);
  const res = await page.request.get("/api/users/me"); // 브라우저와 같은 쿠키로 요청한다

  expect(res.status(), await res.text()).toBe(200);
});

// 명세 4: 로그아웃을 하면 → 세션 쿠키는 만료된다
test("명세 4: 로그아웃하면 세션 쿠키가 사라진다", async ({ page, context }) => {
  await login(page);
  await logout(page);
  const cookies = await sessionCookies(context); // 만료된 쿠키는 브라우저가 지우므로 목록에 남지 않는다

  expect(cookies.length, "세션 쿠키가 남아 있다 (로그아웃 실패?)").toBe(0);
});

// 명세 5: 로그아웃을 하면 → 로그인이 필요한 화면에 들어가면 로그인 화면으로 보내진다
test("명세 5: 로그아웃 뒤 보호 화면에 들어가면 로그인 화면으로 간다", async ({ page }) => {
  await login(page);
  await logout(page);
  await page.goto("/instructor");

  await expect(page).toHaveURL(/\/login/);
});
