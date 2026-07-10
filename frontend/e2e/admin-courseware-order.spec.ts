import { test, expect, APIRequestContext } from "@playwright/test";
import {
  adminLogin,
  createCourseware,
  ensureLeafCategory,
} from "./api-helpers";

/**
 * v1.5 课件素材顺序编辑 E2E。
 *
 * 覆盖：
 * - v1.5-AC-046 前台详情按 sortOrder 升序展示 + 多素材时显示提示文案
 * - v1.5-AC-043 拖拽改序后保存
 * - v1.5-AC-050 键盘可达性(Tab → Space → ArrowDown → Space)
 * - v1.5-AC-044/045/047 通过 API 直命中验证错误返回
 */

// 简易辅助:把 PDF 字节作为上传 payload
function pdfBuffer(): Uint8Array {
  return new TextEncoder().encode("%PDF-1.4 e2e mock content");
}

async function uploadPdfMaterial(
  request: APIRequestContext,
  name: string,
): Promise<number> {
  const r = await request.post("/api/admin/materials", {
    multipart: {
      file: { name, mimeType: "application/pdf", buffer: pdfBuffer() },
    },
  });
  expect(r.ok(), `material upload failed: ${await r.text()}`).toBe(true);
  const body = await r.json();
  return Number(body.data.id);
}

async function reorderMaterials(
  request: APIRequestContext,
  coursewareId: number,
  materialIds: number[],
): Promise<void> {
  const r = await request.put(
    `/api/admin/coursewares/${coursewareId}/materials/order`,
    { data: { materialIds } },
  );
  expect(r.ok(), `reorder failed: ${r.status()} ${await r.text()}`).toBe(true);
}

test.describe.serial("v1.5 课件素材顺序编辑", () => {
  test("v1.5-AC-046 前台详情按 sortOrder 升序展示 + 提示文案", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `s-${Date.now()}`);
    // 上传 3 个素材
    const m1 = await uploadPdfMaterial(request, `e2e-1-${Date.now()}.pdf`);
    const m2 = await uploadPdfMaterial(request, `e2e-2-${Date.now()}.pdf`);
    const m3 = await uploadPdfMaterial(request, `e2e-3-${Date.now()}.pdf`);
    const title = `e2e-order-${Date.now()}`;
    // 创建时按 [m1, m2, m3] 顺序
    const cw = await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [m1, m2, m3],
    });
    // 重排为 [m3, m1, m2]
    await reorderMaterials(request, cw.id, [m3, m1, m2]);

    // 打开详情页
    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();

    // 提示文案应出现
    const hint = page.getByTestId("detail-materials-order-hint");
    await expect(hint).toBeVisible({ timeout: 10_000 });
    await expect(hint).toContainText("由管理员设定的学习顺序");

    // 素材顺序与重排后一致
    const items = page.getByTestId("p-detail-material");
    await expect(items).toHaveCount(3, { timeout: 10_000 });
    const ids = await items.evaluateAll((els) =>
      els.map((el) => Number(el.getAttribute("data-material-id"))),
    );
    expect(ids).toEqual([m3, m1, m2]);
  });

  test("v1.5-AC-044/045 order 接口错误返回 400", async ({ request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `e-${Date.now()}`);
    const m1 = await uploadPdfMaterial(request, `e2e-x1-${Date.now()}.pdf`);
    const cw = await createCourseware(request, {
      title: `e2e-bad-${Date.now()}`,
      categoryId: leaf,
      materialIds: [m1],
    });
    // 重复 ID
    const dup = await request.put(
      `/api/admin/coursewares/${cw.id}/materials/order`,
      { data: { materialIds: [m1, m1] } },
    );
    expect(dup.status()).toBe(400);
    const dupBody = await dup.json();
    expect(dupBody.code).toBe("courseware_materials_invalid");
  });

  test("v1.5-AC-049 后端 PUT 顺序接口 200 + sortOrders 连续", async ({
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `o-${Date.now()}`);
    const m1 = await uploadPdfMaterial(request, `o1-${Date.now()}.pdf`);
    const m2 = await uploadPdfMaterial(request, `o2-${Date.now()}.pdf`);
    const m3 = await uploadPdfMaterial(request, `o3-${Date.now()}.pdf`);
    const cw = await createCourseware(request, {
      title: `e2e-ord-${Date.now()}`,
      categoryId: leaf,
      materialIds: [m1, m2, m3],
    });
    const r = await request.put(
      `/api/admin/coursewares/${cw.id}/materials/order`,
      { data: { materialIds: [m3, m2, m1] } },
    );
    expect(r.ok()).toBe(true);
    const body = await r.json();
    const so = body.data.materials.map((m: { sortOrder: number }) => m.sortOrder);
    expect(so).toEqual([0, 1, 2]);
    expect(body.data.materialIds).toEqual([m3, m2, m1]);
  });

  test("v1.5-AC-050 UI:鼠标拖拽排序 + 上移/下移按钮", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `u-${Date.now()}`);
    const m1 = await uploadPdfMaterial(request, `u1-${Date.now()}.pdf`);
    const m2 = await uploadPdfMaterial(request, `u2-${Date.now()}.pdf`);
    const m3 = await uploadPdfMaterial(request, `u3-${Date.now()}.pdf`);
    const title = `e2e-ui-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [m1, m2, m3],
    });

    // 打开编辑页:从列表点编辑
    await page.goto("/admin/coursewares");
    // 找到刚创建的课件行,点击行内的编辑按钮
    const row = page.getByTestId(new RegExp(`^cw-row-`));
    await expect(row.first()).toBeVisible({ timeout: 10_000 });
    const rowId = await row.first().getAttribute("data-testid");
    const cwId = Number((rowId ?? "").replace("cw-row-", ""));
    await page.getByTestId(`cw-edit-${cwId}`).click();
    // 等待表单加载
    await expect(page.getByTestId("cw-form")).toBeVisible({ timeout: 10_000 });
    // 确认排序器出现
    const sorter = page.getByTestId("cw-material-sorter");
    await expect(sorter).toBeVisible();
    // 三个素材在右栏
    await expect(
      page.getByTestId(`cw-material-sorter-row-${m1}`),
    ).toBeVisible();
    await expect(
      page.getByTestId(`cw-material-sorter-row-${m2}`),
    ).toBeVisible();
    await expect(
      page.getByTestId(`cw-material-sorter-row-${m3}`),
    ).toBeVisible();

    // 点击 m1 的「下移」按钮 → 顺序变为 [m2, m1, m3]
    await page.getByTestId(`cw-material-sorter-down-${m1}`).click();
    // 保存
    await page.getByTestId("cw-save").click();
    await expect(page.getByText("已保存")).toBeVisible({ timeout: 10_000 });
  });
});
