import { test, expect } from "@playwright/test";
import { adminLogin, createCourseware, ensureLeafCategory } from "./api-helpers";

/**
 * F-001 ~ F-005:前台 Home 首页。
 * - F-001 显示搜索栏
 * - F-002 显示入口提示
 * - F-003 关键词搜索跳转 RESULT
 * - F-004 关键词查询参数 ?q= 同步初始 view
 * - F-005 空态文案
 */
test.describe.serial("F-001..F-005 首页 Home", () => {
  test.beforeAll(async ({ request }) => {
    await adminLogin(request);
  });

  test("F-001 首页加载并显示搜索栏", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("input[name='q'], input[placeholder*='搜索']").first()).toBeVisible();
  });

  test("F-002 首页有标题与提示文案", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toContainText(/学习|课件|Learning/i);
  });

  test("F-004 URL ?q= 同步初始 view=result", async ({ page, request }) => {
    const leaf = await ensureLeafCategory(request, `pw-home-${Date.now()}`);
    const unique = `homekeyword-${Date.now()}`;
    await createCourseware(request, {
      title: unique,
      categoryId: leaf,
    });

    await page.goto(`/?q=${unique}`);
    // 结果页应列出该课件
    await expect(page.getByText(unique).first()).toBeVisible({ timeout: 10_000 });
  });

  test("F-005 关键词无结果时显示空态", async ({ page }) => {
    await page.goto(`/?q=zzzzznotfound-${Date.now()}`);
    await expect(page.locator("body")).toContainText(/没有|未找到|无结果|暂无/i, {
      timeout: 8000,
    });
  });
});