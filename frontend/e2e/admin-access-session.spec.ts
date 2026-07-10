/**
 * 访问令牌 · 访问记录(usage)页面 E2E。
 *
 * 覆盖:
 * - 列表页点击「访问记录」跳转到 usage 页
 * - usage 页概览卡片 + 素材汇总默认排序
 * - 时间段筛选
 *
 * 依赖:后端 dev 环境已就绪(playwright.config.ts 中 webServer 启动 dev),
 * 管理员 token = "demo"。
 */
import { test, expect, APIRequestContext } from "@playwright/test";
import {
  adminLogin,
  ensureAccessToken,
  ensureLeafCategory,
} from "./api-helpers";

/** 浏览器内 SHA-256(返回 hex) */
async function sha256Hex(input: string): Promise<string> {
  const enc = new TextEncoder().encode(input);
  const buf = await globalThis.crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function startAccessSession(
  request: APIRequestContext,
  materialId: number,
  tokenHash: string,
): Promise<number> {
  const r = await request.post("/api/public/access-sessions", {
    data: { materialId },
    headers: { "X-Token-Hash": tokenHash, "Content-Type": "application/json" },
  });
  if (!r.ok()) {
    throw new Error(
      `access-session start failed: ${r.status()} ${await r.text()}`,
    );
  }
  const body = await r.json();
  return Number(body.data.sessionId);
}

async function leaveAccessSession(
  request: APIRequestContext,
  sessionId: number,
  tokenHash: string,
  durationSeconds: number,
): Promise<void> {
  const r = await request.post(
    `/api/public/access-sessions/${sessionId}/leave`,
    {
      data: { durationSeconds },
      headers: { "X-Token-Hash": tokenHash, "Content-Type": "application/json" },
    },
  );
  expect(r.ok(), `leave failed: ${r.status()} ${await r.text()}`).toBe(true);
}

test.describe.serial("A-TOKEN-USAGE 访问记录", () => {
  test("USAGE-01 列表页操作区可见「访问记录」链接", async ({ page }) => {
    await page.goto("/admin/access-tokens");
    const firstRow = page.locator("[data-testid^='token-row-']").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    const usageLink = firstRow.locator("a[data-testid^='token-usage-']");
    await expect(usageLink).toBeVisible();
    await expect(usageLink).toContainText("访问记录");
  });

  test("USAGE-02 点击「访问记录」跳转到 usage 页面", async ({ page }) => {
    await page.goto("/admin/access-tokens");
    const firstRow = page.locator("[data-testid^='token-row-']").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    const link = firstRow.locator("a[data-testid^='token-usage-']");
    const href = await link.getAttribute("href");
    expect(href).toMatch(/\/admin\/access-tokens\/\d+\/usage$/);
    await link.click();
    await expect(page).toHaveURL(/\/admin\/access-tokens\/\d+\/usage$/);
    await expect(page.locator("h1")).toContainText("访问记录");
  });

  test("USAGE-03 概览卡片 + 素材汇总数据正确", async ({ page, request }) => {
    await adminLogin(request);
    const ts = Date.now().toString(36).slice(-6);
    const token = await ensureAccessToken(request, `e2e-usage-${ts}`);
    const leaf = await ensureLeafCategory(request, `e2eUS${ts}`);

    // 上传 PDF(用 TextEncoder 编码避免依赖 Node Buffer)
    const pdfBytes = new TextEncoder().encode("%PDF-1.4 e2e");
    const up = await request.post("/api/admin/materials", {
      multipart: {
        file: {
          name: "e2e.pdf",
          mimeType: "application/pdf",
          buffer: pdfBytes,
        },
      },
    });
    expect(up.ok(), `material upload failed: ${await up.text()}`).toBe(true);
    const materialId = Number((await up.json()).data.id);

    // 创建 RESTRICTED 课件
    const cw = await request.post("/api/admin/coursewares", {
      data: {
        title: `e2e-cw-${ts}`,
        categoryId: leaf,
        accessMode: "RESTRICTED",
        tokenIds: [token.id],
        materialIds: [materialId],
        tagIds: [],
        description: null,
        author: null,
      },
    });
    expect(cw.ok(), `courseware create failed: ${await cw.text()}`).toBe(true);

    // 灌数据:2 条 session(12s / 7s)
    const tokenHash = await sha256Hex(token.value);
    for (const dur of [12, 7]) {
      const sid = await startAccessSession(request, materialId, tokenHash);
      await leaveAccessSession(request, sid, tokenHash, dur);
    }

    await page.goto(`/admin/access-tokens/${token.id}/usage`);
    await expect(page.locator("h1")).toContainText("访问记录");

    // 总停留 = 19s
    const totalDurCard = page.locator(
      "[data-testid='usage-card-total-duration']",
    );
    await expect(totalDurCard).toContainText("00:19");

    // 概览课件数 = 1
    await expect(
      page.locator("[data-testid='usage-card-courseware-count']"),
    ).toContainText("1");

    // 素材汇总行
    const row = page.locator(
      `[data-testid='usage-summary-row-${materialId}']`,
    );
    await expect(row).toBeVisible({ timeout: 8_000 });
    const durCell = page.locator(
      `[data-testid='usage-summary-duration-${materialId}']`,
    );
    await expect(durCell).toContainText("00:19");
    await expect(row).toContainText("2");
  });

  test("USAGE-04 时间段筛选", async ({ page, request }) => {
    await adminLogin(request);
    const ts = Date.now().toString(36).slice(-6);
    const token = await ensureAccessToken(request, `e2e-usage-flt-${ts}`);

    await page.goto(`/admin/access-tokens/${token.id}/usage`);
    await expect(page.locator("h1")).toContainText("访问记录");

    const startInput = page.locator("[data-testid='usage-start']");
    const endInput = page.locator("[data-testid='usage-end']");
    await expect(startInput).toHaveValue(
      (() => {
        const d = new Date();
        d.setDate(d.getDate() - 6);
        return d.toISOString().slice(0, 10);
      })(),
    );
    await expect(endInput).toHaveValue(new Date().toISOString().slice(0, 10));

    await page.locator("[data-testid='usage-quick-30d']").click();
    const expected = (() => {
      const d = new Date();
      d.setDate(d.getDate() - 29);
      return d.toISOString().slice(0, 10);
    })();
    await expect(startInput).toHaveValue(expected);
  });

  test("USAGE-04b 快捷「本月」按钮", async ({ page, request }) => {
    await adminLogin(request);
    const ts = Date.now().toString(36).slice(-6);
    const token = await ensureAccessToken(request, `e2e-usage-month-${ts}`);

    await page.goto(`/admin/access-tokens/${token.id}/usage`);
    await expect(page.locator("h1")).toContainText("访问记录");

    const startInput = page.locator("[data-testid='usage-start']");
    const endInput = page.locator("[data-testid='usage-end']");

    // 点击「本月」后,start 应为本月 1 号,end 仍为今天
    await page.locator("[data-testid='usage-quick-month']").click();
    const monthStart = (() => {
      const d = new Date();
      return new Date(d.getFullYear(), d.getMonth(), 1)
        .toISOString()
        .slice(0, 10);
    })();
    await expect(startInput).toHaveValue(monthStart);
    await expect(endInput).toHaveValue(new Date().toISOString().slice(0, 10));
  });

  test("USAGE-05 访问台账 Tab 切换", async ({ page, request }) => {
    await adminLogin(request);
    const ts = Date.now().toString(36).slice(-6);
    const token = await ensureAccessToken(request, `e2e-usage-ledger-${ts}`);

    await page.goto(`/admin/access-tokens/${token.id}/usage`);
    await page.locator("[data-testid='usage-tab-ledger']").click();
    await expect(
      page.locator("[data-testid='usage-ledger-empty']"),
    ).toBeVisible({ timeout: 5_000 });
  });
});
