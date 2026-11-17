// 브라우저 테스트(Playwright) 설정
// 실제 Supabase 로그인이 필요해 CI 에서는 돌리지 않는다. 실행 방법은 Makefile `webe2e`.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    // 웹(make web)과 백엔드(make api)를 먼저 띄워 둔다
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
