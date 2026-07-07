import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E 配置:针对已部署的 docker-compose 服务。
 * - 5173:前端 nginx (已构建 SPA)
 * - 8000:后端 FastAPI
 *
 * 与后端 docker-compose 共用同一份数据,所以测试需要幂等或使用唯一 label。
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: process.env.LH_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
  expect: {
    timeout: 10000,
  },
  timeout: 60_000,
});