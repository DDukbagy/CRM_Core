// 화면 점검: 실제 화면 클릭·입력 → DB·화면 문구로 확인. 사용: node run.mjs web|instructor|customer [이름 일부]
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs";

const I = JSON.parse(fs.readFileSync(new URL("./ids.json", import.meta.url)));
const q = sql => { try { return execFileSync("docker", ["exec", "crm-local-db", "psql", "-U", "postgres", "-d", "crm_ui", "-Atc", sql]).toString().trim(); } catch { return "SQL오류"; } };
const SHOTS = new URL("./shots/", import.meta.url).pathname;
const D = new Date(); const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const SUITES = {
  web: { base: "http://127.0.0.1:3000", web: true, vp: { width: 1366, height: 900 }, flows: [
    { name: "웹 레슨노트 > 작성", user: "kim",
      steps: [["goto", "/instructor/notes"], ["click", "노트 작성"], ["click", "정고객", { exact: true, last: true }],
              ["fill", "예: 3회차 레슨", "웹 노트"], ["fill", "레슨 내용, 피드백, 다음 레슨 목표...", "웹에서 쓴 노트"], ["click", "저장", { exact: true, last: true }]],
      check: `select count(*) from lesson_notes where title='웹 노트' and customer_id='${I.c2}'`, expect: "1" },
    { name: "웹 레슨노트 > 목록·고객별 보기·수정", user: "kim",
      steps: [["goto", "/instructor/notes"], ["expectText", "1회차"], ["click", "정고객", { exact: true }], ["noText", "1회차"], ["click", "웹 노트"],
              ["fill", "레슨 내용, 피드백, 다음 레슨 목표...", "웹에서 고친 노트"], ["click", "저장", { exact: true, last: true }]],
      check: "select content from lesson_notes where title='웹 노트'", expect: "웹에서 고친 노트" },
    { name: "웹 프로모션 > 만들기(10회권 10%)", user: "kim",
      steps: [["goto", "/instructor/promotions"], ["click", "프로모션 만들기"], ["fill", "예: 가을맞이 10회권 할인", "가을 할인"],
              ["select", "대상 수강권", "10회권"], ["click", "저장", { exact: true, last: true }], ["expectText", "진행 중"], ["expectText", "450,000원"]],
      check: "select count(*) from promotions where title='가을 할인' and discount_type='PERCENT' and discount_value=10", expect: "1" },
    { name: "웹 프로모션 > 중지 → 다시 켜기", user: "kim",
      steps: [["goto", "/instructor/promotions"], ["click", "중지", { exact: true }], ["expectText", "다시 켜기"], ["click", "다시 켜기", { exact: true }]],
      check: "select is_active::text from promotions where title='가을 할인'", expect: "true" },
    { name: "웹 프로모션 > 잘못된 할인율 안내", user: "kim",
      steps: [["goto", "/instructor/promotions"], ["click", "프로모션 만들기"], ["fill", "예: 가을맞이 10회권 할인", "잘못"], ["fillNumber", 0, "150"],
              ["click", "저장", { exact: true, last: true }], ["expectText", "할인율은 1~100"]],
      check: "select count(*) from promotions where title='잘못'", expect: "0" },
    { name: "웹 매출 분석 > 대시보드", user: "kim",
      steps: [["goto", "/instructor/insights"], ["expectText", "620,000원"], ["expectText", "월별 매출"], ["expectText", "10회권"], ["expectText", "계좌이체"]],
      check: "select 'ok'", expect: "ok" },
    { name: "웹 사이드바 > 새 메뉴 3개", user: "kim",
      steps: [["goto", "/instructor"], ["expectText", "레슨노트"], ["expectText", "매출 분석"], ["expectText", "프로모션"]],
      check: "select 'ok'", expect: "ok" },
  ] },
  instructor: { base: "http://127.0.0.1:8082", vp: { width: 390, height: 844 }, flows: [
    { name: "앱 매출 탭 > 운영 현황(확인 전용)", user: "kim",
      steps: [["goto", "/revenue"], ["click", "📊 매출 분석 · 프로모션 보기"], ["expectText", "확인 전용 화면"], ["expectText", "620,000원"],
              ["expectText", "가을 할인"], ["expectText", "10% 할인"], ["noText", "프로모션 만들기"]],
      check: "select 'ok'", expect: "ok" },
  ] },
  customer: { base: "http://127.0.0.1:8081", vp: { width: 390, height: 844 }, flows: [
    { name: "고객 수강권 탭 > 진행 중 프로모션·할인가", user: "c1",
      steps: [["goto", "/passes"], ["expectText", "가을 할인"], ["expectText", "10% 할인"], ["expectText", "450,000원"]],
      check: "select 'ok'", expect: "ok" },
    { name: "고객 레슨노트 > 웹에서 쓴 노트는 다른 고객 것이라 안 보임", user: "c1",
      steps: [["goto", "/notes"], ["expectText", "1회차"], ["noText", "웹 노트"]],
      check: "select 'ok'", expect: "ok" },
  ] },
};

const [which, only] = process.argv.slice(2);
const suite = SUITES[which];
const browser = await chromium.launch({ channel: "chromium", args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"] });
const out = [];
for (const [n, f] of suite.flows.entries()) {
  if (only && !f.name.includes(only)) continue;
  const page = await browser.newPage({ viewport: suite.vp, locale: "ko-KR", timezoneId: "Asia/Seoul" });
  const notes = [];
  page.on("dialog", async d => { notes.push(`${d.type()}: ${d.message().replace(/\n+/g, " / ").slice(0, 90)}`); await d.accept(); });
  page.on("response", r => { const u = r.url(); if ((u.includes(":8000/") || u.includes("/api/")) && r.status() >= 400) notes.push(`HTTP ${r.status()} ${r.request().method()} ${u.replace(/^https?:\/\/[^/]+/, "")}`); });
  page.on("pageerror", e => notes.push(`pageerror: ${String(e).slice(0, 140)}`));
  const settle = async () => { await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {}); await page.waitForTimeout(1200); };
  const W = suite.vp.width;
  const inView = async (text, exact) => {
    const all = page.getByText(text, { exact }).filter({ visible: true });
    const res = [];
    for (let k = 0; k < await all.count(); k++) {
      const bx = await all.nth(k).boundingBox();
      if (bx && bx.x >= 0 && bx.x + bx.width <= W + 1) res.push(all.nth(k));
    }
    return res;
  };
  let error = "";
  try {
    if (suite.web) {
      await page.goto(suite.base + "/login", { timeout: 120000 }); await settle();
      await page.locator('input[type="email"]').fill(`${f.user}@example.com`); await page.locator('input[type="password"]').fill("test1234");
      await page.locator('button[type="submit"]').click();
    } else {
      await page.goto(suite.base + "/", { timeout: 120000 }); await settle();
      await page.getByPlaceholder("이메일").fill(`${f.user}@example.com`, { timeout: 60000 }); await page.getByPlaceholder("비밀번호").fill("test1234");
      await page.getByText("로그인", { exact: true }).last().click();
    }
    await page.waitForFunction(() => !location.pathname.includes("login"), null, { timeout: 30000 }); await settle();
    for (const [si, [kind, a, b]] of f.steps.entries()) {
      error = `단계 ${si + 1} (${kind} ${String(a).slice(0, 24)})`;
      if (kind === "goto") { await page.goto(suite.base + a); await settle(); continue; }
      if (kind === "fill") { await page.getByPlaceholder(a, { exact: true }).filter({ visible: true }).last().fill(b, { timeout: 15000 }); continue; }
      if (kind === "fillNumber") { await page.locator('input[type="number"]').nth(a).fill(b); continue; }
      if (kind === "select") {
        const sel = page.locator("select").filter({ has: page.locator("option", { hasText: b }) }).first();
        const val = await sel.locator("option", { hasText: b }).first().getAttribute("value");
        await sel.selectOption(val); continue;
      }
      if (kind === "expectText" || kind === "noText") {
        await page.waitForTimeout(800);
        const cnt = (await inView(a, false)).length;
        if (kind === "expectText" && cnt === 0) throw new Error(`화면에 없음: ${a}`);
        if (kind === "noText" && cnt > 0) throw new Error(`있으면 안 됨: ${a}`);
        continue;
      }
      const o = b || {};
      const list = await inView(a, !!o.exact);
      if (!list.length) throw new Error(`화면에 없음: ${a}`);
      const loc = o.last ? list.at(-1) : list[0];
      try { await loc.click({ timeout: 6000 }); }
      catch { const bx = await loc.boundingBox(); await page.mouse.click(bx.x + bx.width / 2, bx.y + bx.height / 2); }
      await page.waitForTimeout(1800);
    }
    await page.waitForTimeout(2000);
    error = "";
  } catch (e) { error = `${error}: ` + String(e).split("\n")[0].slice(0, 120); }
  const got = q(f.check);
  await page.screenshot({ path: `${SHOTS}${which}-${n}.png`, fullPage: true });
  out.push({ ok: got === f.expect && !error, name: f.name, got, expect: f.expect, error, notes });
  await page.close();
}
await browser.close();
for (const r of out) {
  console.log(`${r.ok ? "✅" : "❌"} ${r.name}  →  ${r.got}${r.got === r.expect ? "" : ` (기대 ${r.expect})`}${r.error ? "  | " + r.error : ""}`);
  for (const nt of [...new Set(r.notes)]) if (!/HTTP 401 GET/.test(nt) && !/_rsc=/.test(nt)) console.log(`     · ${nt}`);
}
