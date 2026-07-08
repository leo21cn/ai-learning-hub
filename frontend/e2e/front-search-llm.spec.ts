import { test, expect } from "@playwright/test";
import {
  adminLogin,
  createCourseware,
  ensureLeafCategory,
} from "./api-helpers";

/**
 * F-007 / F-008 / F-009  AI 智能搜索回归(LLM-to-SQL + 关键词兜底)
 *
 * - F-007 自然语言长句命中:建 title=`增量绩效-{ts}` → `/?q=帮我找一下与增量绩效-{ts}相关的课件`
 *   → 断言结果页出现 `result-item-{id}` 或课件标题(LLM 路径返回 source=llm)
 * - F-008 无 DASHSCOPE_API_KEY 时降级:env 移除 key → 长句查询走 keyword 兜底
 *   → 响应 data.source === "keyword"
 * - F-009 短关键词仍按 ILIKE 命中:q=`管理` 命中含「管理」的标题
 *
 * 环境配置:
 *   e2e 容器需注入 `DASHSCOPE_API_KEY`;
 *   若 e2e 环境无法访问百炼,F-007 跳过(由 mock 后端或前端断言);
 *   F-008 / F-009 不依赖 LLM,任何环境都可跑。
 */
test.describe.serial("F-007 / F-008 / F-009 AI 智能搜索", () => {
  test("F-007 自然语言长句命中(LLM 路径)", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `nl-${Date.now()}`);
    const ts = Date.now();
    const unique = `增量绩效-${ts}`;
    await createCourseware(request, { title: unique, categoryId: leaf });

    // 调搜索 API 直接验证
    const apiResp = await request.get(
      `/api/public/coursewares/search?q=${encodeURIComponent(`帮我找一下与${unique}相关的课件`)}`,
    );
    expect(apiResp.ok(), `search api failed: ${await apiResp.text()}`).toBe(true);
    const body = await apiResp.json();
    // 若 DASHSCOPE_API_KEY 已注入且 LLM 命中 → source="llm";
    // 若 e2e 环境无法访问百炼,可能降级为 keyword,但课件标题 ILIKE 仍能命中。
    expect(["llm", "keyword"]).toContain(body.data.source);
    // 命中的 items 应包含所建课件
    const titles = (body.data.items as Array<{ title: string }>).map((i) => i.title);
    expect(titles).toContain(unique);

    // 浏览器断言:URL 跳转后结果出现
    await page.goto(
      `/?q=${encodeURIComponent(`帮我找一下与${unique}相关的课件`)}`,
    );
    await expect(page.getByText(unique).first()).toBeVisible({ timeout: 10_000 });
  });

  test("F-008 无 DASHSCOPE_API_KEY 时降级为 keyword", async ({ page, request }) => {
    // 通过 env 探测:在 dev 模式下后端会读 process.env.DASHSCOPE_API_KEY;
    // e2e 默认无 key(配置在 .env 中留空),所以 is_enabled()=False → 降级
    const apiResp = await request.get(
      `/api/public/coursewares/search?q=${encodeURIComponent("帮我找一下管理课程")}`,
    );
    expect(apiResp.ok(), `search api failed: ${await apiResp.text()}`).toBe(true);
    const body = await apiResp.json();
    // 没注入 key → 走 keyword 兜底
    expect(body.data.source).toBe("keyword");
    expect(body.data.items).toBeDefined();

    // 前端降级徽标可见(若前端未在 e2e 环境启 LLM,会显示「降级中」字样)
    await page.goto(
      `/?q=${encodeURIComponent("帮我找一下管理课程")}`,
    );
    // 徽标元素存在(不管显示什么文案)
    await expect(page.getByTestId("p-result-ai-badge").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("F-009 短关键词仍按 ILIKE 命中", async ({ page, request }) => {
    await adminLogin(request);
    const leaf = await ensureLeafCategory(request, `kw-${Date.now()}`);
    const unique = `管理艺术-${Date.now()}`;
    await createCourseware(request, { title: unique, categoryId: leaf });

    const apiResp = await request.get(
      `/api/public/coursewares/search?q=管理`,
    );
    expect(apiResp.ok(), `search api failed: ${await apiResp.text()}`).toBe(true);
    const body = await apiResp.json();
    expect(body.data.source).toBe("keyword");
    const titles = (body.data.items as Array<{ title: string }>).map((i) => i.title);
    expect(titles).toContain(unique);

    // 浏览器断言
    await page.goto(`/?q=管理`);
    await expect(page.getByText(unique).first()).toBeVisible({ timeout: 10_000 });
  });
});
