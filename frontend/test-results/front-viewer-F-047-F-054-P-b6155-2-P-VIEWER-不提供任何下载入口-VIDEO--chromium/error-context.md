# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: front-viewer.spec.ts >> F-047..F-054 P-VIEWER 在线浏览 >> F-052 P-VIEWER 不提供任何下载入口(VIDEO)
- Location: e2e\front-viewer.spec.ts:196:3

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByTestId('p-detail-material-browse-btn').first()

```

# Page snapshot

```yaml
- main [ref=e4]:
  - generic [ref=e5]:
    - button "← 返回首页" [ref=e6] [cursor=pointer]
    - heading "搜索结果 \"f052-course-1783476233322\"" [level=1] [ref=e7]:
      - text: 搜索结果
      - generic [ref=e8]: "\"f052-course-1783476233322\""
    - paragraph [ref=e9]:
      - text: 共 1 条结果
      - generic "LLM 不可用,已自动降级到关键词搜索" [ref=e10]: AI 智能搜索· 降级中
  - list [ref=e11]:
    - listitem [ref=e12] [cursor=pointer]:
      - generic [ref=e13]:
        - heading "f052-course-1783476233322" [level=2] [ref=e15]
        - generic [ref=e16]: 开放
```

# Test source

```ts
  117 |     const info = page.getByTestId("p-viewer-video-info");
  118 |     await expect(info).toBeVisible();
  119 |     // 文件名展示
  120 |     await expect(info).toContainText(/\.mp4$/);
  121 |     // 类型 + 大小
  122 |     await expect(info).toContainText(/视频/);
  123 |     // v1.2 起 P-VIEWER 不再提供下载入口
  124 |     await expect(page.getByTestId("p-viewer-download-link")).toHaveCount(0);
  125 |     await expect(
  126 |       page.locator('[data-testid="p-viewer-video-root"] a:has-text("下载到本地")'),
  127 |     ).toHaveCount(0);
  128 |   });
  129 | 
  130 |   test("F-049 P-VIEWER-PDF PDF Word 式阅读(工具条 + 页码气泡)", async ({
  131 |     page,
  132 |     request,
  133 |   }) => {
  134 |     await adminLogin(request);
  135 |     const leaf = await ensureLeafCategory(request, `f049-${Date.now()}`);
  136 |     // 简单 PDF 二进制(只要 FastAPI 接受 + 后端能下发即可)
  137 |     const mid = await uploadMaterial(
  138 |       request,
  139 |       `f049-${Date.now()}.pdf`,
  140 |       toBytes("%PDF-1.4 minimal pdf body for test"),
  141 |       "application/pdf",
  142 |     );
  143 |     const title = `f049-course-${Date.now()}`;
  144 |     await createCourseware(request, {
  145 |       title,
  146 |       categoryId: leaf,
  147 |       materialIds: [mid],
  148 |     });
  149 | 
  150 |     await page.goto(`/?q=${title}`);
  151 |     await page.getByText(title).first().click();
  152 |     await page.getByTestId("p-detail-material-browse-btn").first().click();
  153 |     await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
  154 | 
  155 |     // PDF 容器出现
  156 |     const pdf = page.getByTestId("p-viewer-pdf");
  157 |     await expect(pdf).toBeVisible({ timeout: 20_000 });
  158 |     // 工具条存在
  159 |     await expect(page.getByTestId("p-viewer-pdf-toolbar")).toBeVisible();
  160 |     // 页码指示器存在
  161 |     await expect(page.getByTestId("p-viewer-pdf-page-indicator")).toBeVisible();
  162 |     // v1.2 起 P-VIEWER 不再提供下载入口
  163 |     await expect(page.getByTestId("p-viewer-download-link")).toHaveCount(0);
  164 |     await expect(
  165 |       page.locator('[data-testid="p-viewer-pdf-root"] a:has-text("下载到本地")'),
  166 |     ).toHaveCount(0);
  167 |   });
  168 | 
  169 |   test("F-051 P-VIEWER 返回 P-DETAIL(三种样式共用)", async ({
  170 |     page,
  171 |     request,
  172 |   }) => {
  173 |     await adminLogin(request);
  174 |     const leaf = await ensureLeafCategory(request, `f051-${Date.now()}`);
  175 |     const mid = await uploadMaterial(
  176 |       request,
  177 |       `f051-${Date.now()}.mp4`,
  178 |       toBytes("\x00\x00\x00 ftypisom placeholder"),
  179 |       "video/mp4",
  180 |     );
  181 |     const title = `f051-course-${Date.now()}`;
  182 |     await createCourseware(request, {
  183 |       title,
  184 |       categoryId: leaf,
  185 |       materialIds: [mid],
  186 |     });
  187 | 
  188 |     await page.goto(`/?q=${title}`);
  189 |     await page.getByText(title).first().click();
  190 |     await page.getByTestId("p-detail-material-browse-btn").first().click();
  191 |     await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
  192 |     await page.getByTestId("p-viewer-back-btn").click();
  193 |     await expect(page).toHaveURL(/view=detail/, { timeout: 10_000 });
  194 |   });
  195 | 
  196 |   test("F-052 P-VIEWER 不提供任何下载入口(VIDEO)", async ({
  197 |     page,
  198 |     request,
  199 |   }) => {
  200 |     await adminLogin(request);
  201 |     const leaf = await ensureLeafCategory(request, `f052-${Date.now()}`);
  202 |     const mid = await uploadMaterial(
  203 |       request,
  204 |       `f052-${Date.now()}.mp4`,
  205 |       toBytes("\x00\x00\x00 ftypisom placeholder"),
  206 |       "video/mp4",
  207 |     );
  208 |     const title = `f052-course-${Date.now()}`;
  209 |     await createCourseware(request, {
  210 |       title,
  211 |       categoryId: leaf,
  212 |       materialIds: [mid],
  213 |     });
  214 | 
  215 |     await page.goto(`/?q=${title}`);
  216 |     await page.getByText(title).first().click();
> 217 |     await page.getByTestId("p-detail-material-browse-btn").first().click();
      |                                                                    ^ Error: locator.click: Test timeout of 60000ms exceeded.
  218 |     await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
  219 | 
  220 |     // P-VIEWER-VIDEO 根可见
  221 |     await expect(page.getByTestId("p-viewer-video-root")).toBeVisible({
  222 |       timeout: 15_000,
  223 |     });
  224 |     // 1) p-viewer-download-link 不存在
  225 |     await expect(page.getByTestId("p-viewer-download-link")).toHaveCount(0);
  226 |     // 2) VIDEO 根作用域内不含文字链接 "下载到本地"
  227 |     await expect(
  228 |       page.locator(
  229 |         '[data-testid="p-viewer-video-root"] a:has-text("下载到本地")',
  230 |       ),
  231 |     ).toHaveCount(0);
  232 |     // 3) 顶栏 / 信息面板中不含任何 href 指向 /api/public/materials/{id}/file 的 a / button
  233 |     const viewerScope = '[data-testid="p-viewer-video-root"]';
  234 |     const downloadTargets = page.locator(
  235 |       `${viewerScope} a[href*="/api/public/materials/"], ${viewerScope} button[data-download-url]`,
  236 |     );
  237 |     await expect(downloadTargets).toHaveCount(0);
  238 |     // 4) 同时验证 P-DETAIL 仍保留下载入口(本任务不覆盖 P-DETAIL)
  239 |     await page.getByTestId("p-viewer-back-btn").click();
  240 |     await expect(page).toHaveURL(/view=detail/, { timeout: 10_000 });
  241 |     await expect(
  242 |       page.getByTestId("p-detail-material-download-link").first(),
  243 |     ).toBeVisible();
  244 |   });
  245 | 
  246 |   test("F-052 P-VIEWER 不提供任何下载入口(PDF)", async ({
  247 |     page,
  248 |     request,
  249 |   }) => {
  250 |     await adminLogin(request);
  251 |     const leaf = await ensureLeafCategory(request, `f052b-${Date.now()}`);
  252 |     const mid = await uploadMaterial(
  253 |       request,
  254 |       `f052b-${Date.now()}.pdf`,
  255 |       toBytes("%PDF-1.4 minimal pdf body"),
  256 |       "application/pdf",
  257 |     );
  258 |     const title = `f052b-course-${Date.now()}`;
  259 |     await createCourseware(request, {
  260 |       title,
  261 |       categoryId: leaf,
  262 |       materialIds: [mid],
  263 |     });
  264 | 
  265 |     await page.goto(`/?q=${title}`);
  266 |     await page.getByText(title).first().click();
  267 |     await page.getByTestId("p-detail-material-browse-btn").first().click();
  268 |     await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
  269 | 
  270 |     await expect(page.getByTestId("p-viewer-pdf-root")).toBeVisible({
  271 |       timeout: 20_000,
  272 |     });
  273 |     await expect(page.getByTestId("p-viewer-download-link")).toHaveCount(0);
  274 |     await expect(
  275 |       page.locator('[data-testid="p-viewer-pdf-root"] a:has-text("下载到本地")'),
  276 |     ).toHaveCount(0);
  277 |     const downloadTargets = page.locator(
  278 |       '[data-testid="p-viewer-pdf-root"] a[href*="/api/public/materials/"]',
  279 |     );
  280 |     await expect(downloadTargets).toHaveCount(0);
  281 |   });
  282 | 
  283 |   test("F-054 P-VIEWER-PDF 缩放控件", async ({ page, request }) => {
  284 |     await adminLogin(request);
  285 |     const leaf = await ensureLeafCategory(request, `f054-${Date.now()}`);
  286 |     const mid = await uploadMaterial(
  287 |       request,
  288 |       `f054-${Date.now()}.pdf`,
  289 |       toBytes("%PDF-1.4 minimal pdf body"),
  290 |       "application/pdf",
  291 |     );
  292 |     const title = `f054-course-${Date.now()}`;
  293 |     await createCourseware(request, {
  294 |       title,
  295 |       categoryId: leaf,
  296 |       materialIds: [mid],
  297 |     });
  298 | 
  299 |     await page.goto(`/?q=${title}`);
  300 |     await page.getByText(title).first().click();
  301 |     await page.getByTestId("p-detail-material-browse-btn").first().click();
  302 |     await expect(page).toHaveURL(/view=viewer/, { timeout: 10_000 });
  303 |     await expect(page.getByTestId("p-viewer-pdf-toolbar")).toBeVisible({
  304 |       timeout: 15_000,
  305 |     });
  306 | 
  307 |     const label = page.getByTestId("p-viewer-pdf-zoom-label");
  308 |     const initial = await label.textContent();
  309 |     expect(initial).toMatch(/\d+%/);
  310 | 
  311 |     // 连续点击 zoom-in 三次,缩放比例上升
  312 |     const zoomIn = page.getByTestId("p-viewer-pdf-zoom-in");
  313 |     await zoomIn.click();
  314 |     await zoomIn.click();
  315 |     await zoomIn.click();
  316 |     const after = await label.textContent();
  317 |     expect(after).not.toEqual(initial);
```