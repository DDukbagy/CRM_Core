import { chromium } from "playwright";
const b = await chromium.launch({ channel: "chromium", args: ["--disable-dev-shm-usage", "--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 390, height: 844 } });
const base = "http://127.0.0.1:8081";
await p.goto(base + "/"); await p.waitForTimeout(4000);
await p.getByPlaceholder("이메일").fill("c1@example.com"); await p.getByPlaceholder("비밀번호").fill("test1234");
await p.getByText("로그인", { exact: true }).last().click(); await p.waitForTimeout(5000);
let mounts = 0;
p.on("request", r => { if (r.url().includes("/passes/customer-passes") || r.url().includes("/passes/me")) mounts++; });
const look = async label => {
  const t = await p.getByText("10회권").filter({ visible: true }).count();
  const spin = await p.locator('[role="progressbar"]').filter({ visible: true }).count();
  console.log(`${label}: 10회권 보임 ${t}, 로딩 표시 ${spin}, 경로 ${new URL(p.url()).pathname}, 수강권 API 호출 누적 ${mounts}`);
};
const how = process.argv[2];
await p.goto(base + "/passes"); await p.waitForTimeout(4000); await look("처음");
if (how === "back") { await p.getByText("게시글", { exact: true }).last().click(); await p.waitForTimeout(2000); await look("게시글 탭"); await p.goBack(); }
else if (how === "menu") {
  await p.getByText("게시글", { exact: true }).last().click(); await p.waitForTimeout(2000); await look("게시글 탭");
  // ☰ 버튼: 화면 제목(h1)과 같은 높이, 왼쪽 끝
  const h = await p.locator('h1:text-is("게시글")').filter({ visible: true }).first().boundingBox();
  await p.mouse.click(30, h.y + h.height / 2);
  await p.waitForTimeout(1200); 
  const hits = await p.locator('[role="button"]').filter({ visible: true }).evaluateAll(els => els.map(e => { const r = e.getBoundingClientRect(); return `${Math.round(r.x)},${Math.round(r.y)} ${e.innerText.slice(0,10)}`; }));
  console.log("버튼들:", hits.slice(0, 12).join(" | "));
  await p.locator(":text-is(\"수강권\"):not(h1)").filter({ visible: true }).last().click(); await p.waitForTimeout(220);
}
else { await p.getByText("게시글", { exact: true }).last().click(); await p.waitForTimeout(2000); await p.locator('[aria-label="menu"], [data-testid="menu"]').count();
  await p.evaluate(() => { history.pushState({}, "", "/passes"); dispatchEvent(new PopStateEvent("popstate")); }); }
for (const ms of [100, 300, 1000, 3000]) { await p.waitForTimeout(ms); await look(`돌아온 뒤 +${ms}ms`); }
await b.close();
