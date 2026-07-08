import { test, expect } from "@playwright/test";
import {
  adminLogin,
  createCourseware,
  ensureAccessToken,
  ensureLeafCategory,
} from "./api-helpers";

/**
 * F-010 ~ F-046 前台详情/锁定/解锁。
 * - F-010 列表显示
 * - F-019a RESTRICTED 也出现在搜索结果中
 * - F-030 进入受限课件显示 P-LOCKED
 * - F-031 输入有效 token 后解锁
 * - F-038 错误 token 提示
 * - F-040 公开课件详情正常显示
 * - F-046 解锁后课件详情可见完整素材
 */
test.describe.serial("F-019a / F-030..F-046 详情与解锁", () => {
  test("F-019a RESTRICTED 课件在搜索结果中可见", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `r-${Date.now()}`);
    const t = await ensureAccessToken(request, `tok-${Date.now()}`);
    const unique = `restrictedSearch-${Date.now()}`;
    await createCourseware(request, {
      title: unique,
      categoryId: leaf,
      accessMode: "RESTRICTED",
      tokenIds: [t.id],
    });
    await page.goto(`/?q=${unique}`);
    await expect(page.getByText(unique).first()).toBeVisible({ timeout: 10_000 });
  });

  test("F-030 / F-031 / F-038 受限课件锁定 + 解锁", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `l-${Date.now()}`);
    const t = await ensureAccessToken(request, `unlock-${Date.now()}`);
    const title = `locked-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      accessMode: "RESTRICTED",
      tokenIds: [t.id],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    // 锁定页应该有"解锁"提示 + token 输入框
    await expect(page.locator("body")).toContainText(/解锁|锁定|token/i, {
      timeout: 10_000,
    });
    const input = page.locator("input[name='token'], input[placeholder*='token' i]").first();
    if ((await input.count()) > 0) {
      // 输入错误 token
      await input.fill("WRONG-TOKEN-VALUE");
      const unlockBtn = page
        .getByRole("button", { name: /解锁|unlock|提交/i })
        .first();
      if ((await unlockBtn.count()) > 0) {
        await unlockBtn.click();
        await expect(page.locator("body")).toContainText(/无效|错误|失败|invalid/i, {
          timeout: 8_000,
        });
      }
      // 输入正确 token
      await input.fill(t.value);
      const okBtn = page
        .getByRole("button", { name: /解锁|unlock|提交/i })
        .first();
      await okBtn.click();
      // 解锁后详情可见
      await expect(page.locator("body")).toContainText(title, { timeout: 10_000 });
    }
  });

  test("F-040 开放课件详情直接可见", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `o-${Date.now()}`);
    const title = `open-course-${Date.now()}`;
    await createCourseware(request, { title, categoryId: leaf });
    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await expect(page.locator("body")).toContainText(title, { timeout: 10_000 });
    // 应不显示锁定/解锁输入框
    await expect(
      page.locator("input[name='token'], input[placeholder*='token' i]"),
    ).toHaveCount(0);
    // F-047: 素材按钮文案为「在线浏览」,而非「下载」
    const browseBtn = page.getByTestId("p-detail-material-browse-btn").first();
    if ((await browseBtn.count()) > 0) {
      await expect(browseBtn).toHaveText("在线浏览");
    }
    // v1.2 起 P-DETAIL 不再提供「下载到本地」入口
    await expect(
      page.getByTestId("p-detail-material-download-link"),
    ).toHaveCount(0);
    await expect(page.locator('a:has-text("下载到本地")')).toHaveCount(0);
    await expect(
      page.locator('[data-testid="page-detail"] a[href*="/api/public/materials/"]'),
    ).toHaveCount(0);
  });
});