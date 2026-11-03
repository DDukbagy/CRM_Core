import { chromium } from "playwright";
const b = await chromium.launch({ channel: "chromium", args: ["--disable-dev-shm-usage", "--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
await p.route("**/api/users/me", async route => {
  const resp = await route.fetch(); const buf = await resp.body(); const h = resp.headers();
  let info = `status=${resp.status()} content-type=${h["content-type"]} content-length=${h["content-length"] ?? "없음"} content-encoding=${h["content-encoding"] ?? "없음"} 실제=${buf.length}바이트`;
  try { const j = JSON.parse(buf.toString()); info += ` role=${j.role} status=${j.status}`; } catch { info += ` JSON 아님, 끝부분: ...${buf.toString().slice(-70)}`; }
  console.log("users/me:", info);
  await route.fulfill({ response: resp, body: buf });
});
await p.goto("https://crm-core-demo-web.vercel.app/login", { timeout: 120000 }); await p.waitForTimeout(3000);
await p.locator('input[type="email"]').fill("instructor@test.com"); await p.locator('input[type="password"]').fill("password"); await p.locator('button[type="submit"]').click();
await p.waitForTimeout(20000);
console.log("현재 경로:", new URL(p.url()).pathname);
await b.close();
