import { test, expect, APIRequestContext } from "@playwright/test";

/**
 * 后端 API 辅助函数:绕过 UI 直接命中 REST,减少 E2E 准备时间。
 */
export async function adminLogin(
  request: APIRequestContext,
  token = "demo",
): Promise<void> {
  const r = await request.post("/api/auth/admin", { data: { token } });
  expect(r.ok(), `admin login failed: ${r.status()} ${await r.text()}`).toBe(
    true,
  );
}

/** 在数据库中创建一棵 3 级分类并返回叶子 id;若已存在同名则复用。 */
export async function ensureLeafCategory(
  request: APIRequestContext,
  prefix: string,
): Promise<number> {
  // 顶层
  let top = await request.post("/api/admin/categories", {
    data: { name: `${prefix}-top` },
  });
  let topBody = await top.json();
  if (!top.ok() && topBody?.code === "category_name_conflict") {
    const list = await request.get("/api/admin/categories");
    const data = await list.json();
    topBody = {
      data: data.data.find(
        (c: { name: string }) => c.name === `${prefix}-top`,
      ),
    };
  }
  const topId = topBody.data.id;

  // 二级
  let mid = await request.post("/api/admin/categories", {
    data: { name: `${prefix}-mid`, parentId: topId },
  });
  let midBody = await mid.json();
  if (!mid.ok() && midBody?.code === "category_name_conflict") {
    const topRes = await request.get(
      `/api/admin/categories/${topId}/children`,
    );
    if (topRes.ok()) {
      const children = await topRes.json();
      midBody = {
        data: children.data.find(
          (c: { name: string }) => c.name === `${prefix}-mid`,
        ),
      };
    }
  }
  const midId = midBody.data.id;

  // 三级叶子
  // 名称最长 30 字符；用 hash + 时间戳后 6 位保证幂等且避免超长。
  const ts = Date.now().toString(36).slice(-6);
  const leaf = await request.post("/api/admin/categories", {
    data: { name: `${prefix.slice(0, 12)}-l-${ts}`, parentId: midId },
  });
  if (!leaf.ok()) {
    throw new Error(
      `ensureLeafCategory leaf failed: ${leaf.status()} ${await leaf.text()}`,
    );
  }
  const leafBody = await leaf.json();
  return leafBody.data.id;
}

export async function ensureAccessToken(
  request: APIRequestContext,
  label: string,
): Promise<{ id: number; value: string }> {
  const r = await request.post("/api/admin/access-tokens", {
    data: { label },
  });
  expect(r.ok(), `token create failed: ${await r.text()}`).toBe(true);
  const body = await r.json();
  return { id: Number(body.data.id), value: body.data.value };
}

/** 创建开放课件。返回 {id, title}。 */
export async function createCourseware(
  request: APIRequestContext,
  args: {
    title: string;
    categoryId: number;
    accessMode?: "OPEN" | "RESTRICTED";
    tokenIds?: number[];
    tagIds?: number[];
    materialIds?: number[];
  },
): Promise<{ id: number; title: string }> {
  const r = await request.post("/api/admin/coursewares", {
    data: {
      title: args.title,
      categoryId: args.categoryId,
      accessMode: args.accessMode ?? "OPEN",
      tokenIds: args.tokenIds ?? [],
      tagIds: args.tagIds ?? [],
      materialIds: args.materialIds ?? [],
      description: null,
      author: null,
    },
  });
  expect(r.ok(), `courseware create failed: ${await r.text()}`).toBe(true);
  const body = await r.json();
  return { id: Number(body.data.id), title: body.data.title };
}