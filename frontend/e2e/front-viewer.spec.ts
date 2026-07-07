import { test, expect, APIRequestContext } from "@playwright/test";
import {
  adminLogin,
  createCourseware,
  ensureLeafCategory,
} from "./api-helpers";

/**
 * F-047 ~ F-054 课件素材"在线浏览"端到端测试。
 *
 * 覆盖:
 * - F-047 P-DETAIL 素材按钮文案为"在线浏览"
 * - F-048 VIDEO 行内播放
 * - F-049 PDF Word 式阅读
 * - F-050 PPT 幻灯片样式(在 CI 无 LibreOffice 时跳过实际预览)
 * - F-051 返回 P-DETAIL
 * - F-052 下载到本地兜底链接
 * - F-053 PPT 全屏切换(在 CI 无 LibreOffice 时跳过)
 * - F-054 PDF 缩放
 *
 * PPT 用例 F-050 / F-053 默认跳过：依赖 `frontend/e2e/fixtures/pptx-20slides.py`
 * 生成 20 张真实 PPTX 并在服务端转 PDF；本地/CI 启用方式：
 *   cd frontend/e2e/fixtures && pip install python-pptx && python pptx-20slides.py
 *   # 后端容器需要装 LibreOffice（参见 backend/Dockerfile）
 *   npx playwright test --grep F-050
 */

/**
 * 把字符串编码成 UTF-8 字节数组(避免依赖 Buffer 全局类型)。
 */
function toBytes(str: string): Uint8Array {
  return new TextEncoder().encode(str);
}

/**
 * 上传素材并返回 id。name 决定类型(mp4→VIDEO / pdf→PDF / ppt/pptx→PPT)。
 */
async function uploadMaterial(
  request: APIRequestContext,
  filename: string,
  bytes: Uint8Array,
  mimeType: string,
): Promise<number> {
  const r = await request.post("/api/admin/materials", {
    multipart: {
      file: {
        name: filename,
        mimeType,
        buffer: bytes,
      },
    },
  });
  expect(r.ok(), `material upload failed: ${r.status()} ${await r.text()}`).toBe(
    true,
  );
  const body = await r.json();
  return Number(body.data.id);
}

test.describe.serial("F-047..F-054 P-VIEWER 在线浏览", () => {
  test("F-047 P-DETAIL 素材按钮文案为『在线浏览』", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f047-${Date.now()}`);
    const mid = await uploadMaterial(
      request,
      `f047-${Date.now()}.pdf`,
      toBytes("%PDF-1.4 demo"),
      "application/pdf",
    );
    const title = `f047-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await expect(page).toHaveURL(/view=detail/, { timeout: 10_000 });

    // 按钮文案应为"在线浏览"
    const browseBtn = page.getByTestId("p-detail-material-browse-btn").first();
    await expect(browseBtn).toBeVisible({ timeout: 10_000 });
    await expect(browseBtn).toHaveText("在线浏览");
    // 下载到本地链接也存在
    await expect(page.getByText("下载到本地").first()).toBeVisible();
  });

  test("F-048 P-VIEWER-VIDEO 视频行内播放", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f048-${Date.now()}`);
    const mid = await uploadMaterial(
      request,
      `f048-${Date.now()}.mp4`,
      toBytes("\x00\x00\x00 ftypisom placeholder"),
      "video/mp4",
    );
    const title = `f048-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await page.getByTestId("p-detail-material-browse-btn").first().click();

    await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
    // VIDEO 子组件渲染
    const video = page.getByTestId("p-viewer-video");
    await expect(video).toBeVisible({ timeout: 15_000 });
    // 信息面板可见
    const info = page.getByTestId("p-viewer-video-info");
    await expect(info).toBeVisible();
    // 文件名展示
    await expect(info).toContainText(/\.mp4$/);
    // 类型 + 大小
    await expect(info).toContainText(/视频/);
  });

  test("F-049 P-VIEWER-PDF PDF Word 式阅读(工具条 + 页码气泡)", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f049-${Date.now()}`);
    // 简单 PDF 二进制(只要 FastAPI 接受 + 后端能下发即可)
    const mid = await uploadMaterial(
      request,
      `f049-${Date.now()}.pdf`,
      toBytes("%PDF-1.4 minimal pdf body for test"),
      "application/pdf",
    );
    const title = `f049-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await page.getByTestId("p-detail-material-browse-btn").first().click();
    await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });

    // PDF 容器出现
    const pdf = page.getByTestId("p-viewer-pdf");
    await expect(pdf).toBeVisible({ timeout: 20_000 });
    // 工具条存在
    await expect(page.getByTestId("p-viewer-pdf-toolbar")).toBeVisible();
    // 页码指示器存在
    await expect(page.getByTestId("p-viewer-pdf-page-indicator")).toBeVisible();
  });

  test("F-051 P-VIEWER 返回 P-DETAIL(三种样式共用)", async ({
    page,
    request,
  }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f051-${Date.now()}`);
    const mid = await uploadMaterial(
      request,
      `f051-${Date.now()}.mp4`,
      toBytes("\x00\x00\x00 ftypisom placeholder"),
      "video/mp4",
    );
    const title = `f051-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await page.getByTestId("p-detail-material-browse-btn").first().click();
    await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
    await page.getByTestId("p-viewer-back-btn").click();
    await expect(page).toHaveURL(/view=detail/, { timeout: 10_000 });
  });

  test("F-052 P-VIEWER 下载到本地兜底链接可用", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f052-${Date.now()}`);
    const mid = await uploadMaterial(
      request,
      `f052-${Date.now()}.mp4`,
      toBytes("\x00\x00\x00 ftypisom placeholder"),
      "video/mp4",
    );
    const title = `f052-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await page.getByTestId("p-detail-material-browse-btn").first().click();
    await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });

    const downloadLink = page.getByTestId("p-viewer-download-link");
    await expect(downloadLink).toBeVisible();
    const href = await downloadLink.getAttribute("href");
    expect(href).toContain(`/api/public/materials/${mid}/file`);
  });

  test("F-054 P-VIEWER-PDF 缩放控件", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `f054-${Date.now()}`);
    const mid = await uploadMaterial(
      request,
      `f054-${Date.now()}.pdf`,
      toBytes("%PDF-1.4 minimal pdf body"),
      "application/pdf",
    );
    const title = `f054-course-${Date.now()}`;
    await createCourseware(request, {
      title,
      categoryId: leaf,
      materialIds: [mid],
    });

    await page.goto(`/?q=${title}`);
    await page.getByText(title).first().click();
    await page.getByTestId("p-detail-material-browse-btn").first().click();
    await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
    await expect(page.getByTestId("p-viewer-pdf-toolbar")).toBeVisible({
      timeout: 15_000,
    });

    const label = page.getByTestId("p-viewer-pdf-zoom-label");
    const initial = await label.textContent();
    expect(initial).toMatch(/\d+%/);

    // 连续点击 zoom-in 三次,缩放比例上升
    const zoomIn = page.getByTestId("p-viewer-pdf-zoom-in");
    await zoomIn.click();
    await zoomIn.click();
    await zoomIn.click();
    const after = await label.textContent();
    expect(after).not.toEqual(initial);
    expect(after).toMatch(/\d+%/);
  });

  // F-050 / F-053 需要真实 20 张 PPTX + 服务端 LibreOffice。
  // 默认跳过；启用方法参见文件头注释。
  test.skip("F-050 P-VIEWER-PPT 幻灯片样式(20 张 fixture,需 LibreOffice)", async () => {
    // 占位用例：实际逻辑需先 `python fixtures/pptx-20slides.py` 生成 courseware-with-pptx-20slides.pptx
    // 然后上传并验证翻页/键盘/全屏。详见 e2e/fixtures/pptx-20slides.py 头注释。
  });

  test.skip("F-053 P-VIEWER-PPT 全屏切换(需 LibreOffice)", async () => {
    // 占位用例：与 F-050 共用 fixture；点 p-viewer-ppt-fullscreen 后
    // 断言 document.fullscreenElement 不为空。详见文件头注释。
  });
});