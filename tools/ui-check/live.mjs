// 배포된 데모에 실제 로그인해 화면·API 오류 확인 (읽기만)
import { chromium } from "playwright";
const b = await chromium.launch({ channel: "chromium", args: ["--disable-dev-shm-usage", "--no-sandbox"] });
const cases = [
  { name: "고객 앱", base: "https://crm-core-demo-customer.vercel.app", email: "customer1@test.com", web: false, after: ["/passes", "/notes", "/chat"], expect: ["10회권", "1회차", "김프로"] },
  { name: "강사 앱", base: "https://crm-core-demo-instructor.vercel.app", email: "instructor@test.com", web: false, after: ["/customers", "/notes"], expect: ["최고객", "1회차"] },
  { name: "웹(강사)", base: "https://crm-core-demo-web.vercel.app", email: "instructor@test.com", web: true, after: ["/instructor/insights", "/instructor/promotions"], expect: ["월별 매출", "가을맞이"] },
];
for (const c of cases) {
  const p = await b.newPage({ viewport: { width: c.web ? 1366 : 390, height: 844 }, locale: "ko-KR", timezoneId: "Asia/Seoul" });
  const errs = [];
  p.on("response", r => { if (r.status() >= 400 && !/favicon/.test(r.url())) errs.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, "").split("?")[0]}`); });
  p.on("console", m => { if (m.type() === "error" && /CORS|Failed to fetch/i.test(m.text())) errs.push("console: " + m.text().slice(0, 100)); });
  let res = "";
  try {
    await p.goto(c.base + "/login", { timeout: 120000 }); await p.waitForTimeout(4000);
    if (c.web) { await p.locator('input[type="email"]').fill(c.email); await p.locator('input[type="password"]').fill("password"); await p.locator('button[type="submit"]').click(); }
    else { await p.getByPlaceholder("이메일").fill(c.email); await p.getByPlaceholder("비밀번호").fill("password"); await p.getByText("로그인", { exact: true }).last().click(); }
    await p.waitForFunction(() => !location.pathname.includes("login"), null, { timeout: 120000 });
    res = `로그인 → ${new URL(p.url()).pathname}`;
    for (const [i, path] of c.after.entries()) {
      await p.goto(c.base + path); await p.waitForLoadState("networkidle", { timeout: 90000 }).catch(() => {}); await p.waitForTimeout(2500);
      const ok = await p.getByText(c.expect[i]).filter({ visible: true }).count();
      res += ` | ${path}: ${ok ? "✅ " + c.expect[i] : "❌ '" + c.expect[i] + "' 안 보임"}`;
    }
  } catch (e) { res += " | 오류: " + String(e).split("\n")[0].slice(0, 120); }
  console.log(`${c.name}: ${res}`);
  for (const e of [...new Set(errs)].filter(e => !/401 GET/.test(e))) console.log("   · " + e);
  await p.close();
}
await b.close();
