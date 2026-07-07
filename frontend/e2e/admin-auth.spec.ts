import { test, expect } from "@playwright/test";
import { adminLogin } from "./api-helpers";

/**
 * A-001 ~ A-006 鉴权后台登录。
 */
test.describe.serial("A-001..A-006 后台登录", () => {
  test("A-001 /admin 重定向到登录页", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/admin\/?$/);
  });

  test("A-002 错误 token 显示错误信息", async ({ page }) => {
    await page.goto("/admin");
    const input = page.locator("input[name='token'], input[type='password']").first();
    await expect(input).toBeVisible();
    await input.fill("wrong-token");
    await page
      .getByRole("button", { name: /登录|login|提交|sign in/i })
      .first()
      .click();
    await expect(page.locator("body")).toContainText(/错误|无效|失败|invalid/i, {
      timeout: 8_000,
    });
  });

  test("A-003 正确 token 登录后跳到管理首页", async ({ page }) => {
    await page.goto("/admin");
    const input = page.locator("input[name='token'], input[type='password']").first();
    await input.fill("demo");
    await page
      .getByRole("button", { name: /登录|login|提交|sign in/i })
      .first()
      .click();
    // 跳到 /admin 或 /admin/categories
    await page.waitForURL(/\/admin(?!\/login)/, { timeout: 10_000 });
  });

  test("A-004 已登录访问 /admin/coursewares 显示课件管理", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    await page.goto("/admin/coursewares");
    await expect(page.locator("body")).toContainText(/课件|courseware/i, {
      timeout: 10_000,
    });
  });

  test("A-005 已登录访问 /admin/access-tokens 显示令牌管理", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    await page.goto("/admin/access-tokens");
    await expect(page.locator("body")).toContainText(/令牌|access.token/i, {
      timeout: 10_000,
    });
  });
});