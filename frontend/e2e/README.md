# Learning Hub 端到端测试(Playwright)

> 本目录存放针对 [Learning Hub](../) 的 E2E 测试,采用 [Playwright](https://playwright.dev/)。
> 服务发现假设 `docker-compose` 已启动并对外暴露 `http://localhost:5173`。

## 一键运行

```bash
cd frontend
npm install                                  # 首次需要
npx playwright install chromium              # 下载 Chromium(国内网络较慢,可设置 PLAYWRIGHT_DOWNLOAD_HOST)
npx playwright test                          # 跑全部
npx playwright test e2e/front-home.spec.ts   # 单文件
```

国内网络加速:

```bash
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright \
  npx playwright install chromium
```

## 依赖的服务

- `lh-frontend` nginx (5173):SPA 静态资源,根路径 `/` 走 React Router
- `lh-backend` FastAPI (8000):REST API,经 vite proxy 转发 `/api/*`

测试默认会:

1. 调用 `POST /api/auth/admin {token:"demo"}` 登录后台,后续 admin API 自动带 Cookie
2. 在数据库中**幂等**创建 3 级分类、AccessToken、课件;`title`/`label` 全部带 `Date.now()` 时间戳避免冲突
3. UI 端只验证 DOM 文本/可访问性,不强依赖 CSS 类名

## 文件清单

| 文件 | 覆盖用例 |
| --- | --- |
| `api-helpers.ts` | 共享 API fixture:adminLogin / ensureLeafCategory / ensureAccessToken / createCourseware |
| `admin-auth.spec.ts` | A-001 ~ A-005 后台登录 + 受保护路由 |
| `front-home.spec.ts` | F-001 ~ F-005 首页 + 搜索跳转 |
| `front-detail.spec.ts` | F-019a / F-030 / F-031 / F-038 / F-040 受限课件锁定与解锁 |

## 已知限制

- Playwright Chromium 体积约 150 MB,首次下载可能超时;若失败可改用系统 Chrome:
  ```ts
  // playwright.config.ts
  use: { ...devices["Desktop Chrome"], channel: "chrome" },
  ```
- 锁定的课件详情页元素可能在 UI 重构后变更 selector,建议用 `data-testid` 标记。
- 与现有 docker-compose 共用同一数据库,删除课件/分类请走管理后台,不要在测试里硬删。