# 跨模块集成 / 受限课件 / 非功能测试用例

> 适用范围：[02-功能需求](../spec/02-功能需求.md) / [06-非功能需求](../spec/06-非功能需求.md) / [07-技术架构](../spec/07-技术架构.md) / [08-验收标准 N01~N09](../spec/08-验收标准.md)。
> 入口：前台 `{BASE}`、后台 `{BASE}/admin`。
> 数据前置：完成 [setup-teardown.md §3](./setup-teardown.md) 全部 Setup 步骤。

---

## 1. 受限课件全链路（FTK）

### FTK-001：首次访问受限课件锁定 → 输入 Token → 解锁

| 项 | 内容 |
| ---- | ---- |
| 前置 | localStorage 干净 |
| 步骤 | 1. 打开 `{BASE}/detail/CW_RESTRICTED`<br>2. 渲染 P-LOCKED<br>3. 输入 `TKN_A` 原值<br>4. 点击解锁 |
| 预期 | - HTTP 200 `ok`<br>- 跳 P-DETAIL<br>- `localStorage.coursewareTokens` 含 `CW_RESTRICTED -> TKN_A 原值` |
| 选择器 | `p-locked-token-input`, `p-locked-unlock-btn`, `p-detail-title` |
| 清理 | 清空 `coursewareTokens` |

### FTK-002：localStorage 命中直接进详情

| 项 | 内容 |
| ---- | ---- |
| 前置 | FTK-001 完成后未清空 |
| 步骤 | 1. 重新打开 `{BASE}/detail/CW_RESTRICTED` |
| 预期 | - 跳过锁定页，直达 P-DETAIL<br>- 不调用 `/access-check`（或调用但直接返回 200） |
| 选择器 | `p-detail-title` |
| 清理 | 清空 |

### FTK-003：Token 失效后清除 localStorage

| 项 | 内容 |
| ---- | ---- |
| 前置 | localStorage 含 `CW_RESTRICTED -> TKN_A 原值` |
| 步骤 | 1. 后台 `POST /api/admin/tokens/TKN_A/revoke`（[10 §3.2.6](../spec/10-API设计规范.md)）<br>2. 前台打开 `{BASE}/detail/CW_RESTRICTED` |
| 预期 | - 前端调 `/access-check` 返回 410 `token_revoked`<br>- 渲染 P-LOCKED<br>- localStorage 中 `CW_RESTRICTED` 项被清空 |
| 选择器 | `p-locked-error` |
| 清理 | 重新生成 `TKN_A` |

### FTK-004：课件切换为开放后旧 Token 无意义

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 切换为 `OPEN` 模式（[04 §3.4](../spec/04-管理后台规格.md)） |
| 步骤 | 1. 打开 `{BASE}/detail/CW_RESTRICTED` |
| 预期 | - 直接渲染 P-DETAIL<br>- localStorage 中旧 Token 项保留但不再被校验 |
| 选择器 | `p-detail-title` |
| 清理 | 恢复为 `RESTRICTED` + 重新绑定 |

### FTK-005：localStorage 初始为空

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无（首次访问） |
| 步骤 | 1. 清空 localStorage<br>2. 打开 `{BASE}` |
| 预期 | - `JSON.parse(localStorage.getItem('coursewareTokens') || '{}')` = `{}` |
| 选择器 | （无） |
| 清理 | 无 |

### FTK-006：5 次错误限流（前端）

| 项 | 内容 |
| ---- | ---- |
| 前置 | P-LOCKED 页面 |
| 步骤 | 1. 连续 5 次错误 Token |
| 预期 | - 第 6 次返回 429 `rate_limited`<br>- 错误文案含"解锁失败，请稍后重试" |
| 选择器 | `p-locked-error` |
| 清理 | 等待 1 分钟 |

### FTK-007：限流解除后可重新解锁

| 项 | 内容 |
| ---- | ---- |
| 前置 | FTK-006 限流中 |
| 步骤 | 1. 等待 60 秒<br>2. 输入正确 Token |
| 预期 | - HTTP 200 `ok`<br>- 成功解锁 |
| 选择器 | `p-detail-title` |
| 清理 | 清空 localStorage |

---

## 2. 前后台鉴权闭环

### AUTH-001：未登录访问受保护接口

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已清空 Cookie |
| 步骤 | 1. `curl GET /api/admin/coursewares`（无 cookie） |
| 预期 | - HTTP 401 `unauthenticated` |
| 选择器 | （无） |
| 清理 | 无 |

### AUTH-002：登录态访问受保护接口

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003 |
| 步骤 | 1. `curl GET /api/admin/coursewares`（带 cookie） |
| 预期 | - HTTP 200 `ok` |
| 选择器 | （无） |
| 清理 | 无 |

### AUTH-003：登录态访问受保护接口（公开部分）

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. `curl GET /api/public/coursewares/search?keyword=项目管理`（无 cookie） |
| 预期 | - HTTP 200 `ok` |
| 选择器 | （无） |
| 清理 | 无 |

---

## 3. 错误码与响应格式一致性

### ERR-001：业务错误响应结构

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 任意业务失败请求 |
| 预期 | - 响应形如：`{ "code": "<string>", "message": "<string>", "data": null, "requestId": "<uuid>" }`<br>- HTTP 状态码与业务码对应（参考 [10 §3.2](../spec/10-API设计规范.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### ERR-002：成功响应结构

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 任意业务成功请求 |
| 预期 | - `{ "code": "ok", "message": "ok", "data": { ... }, "requestId": "..." }` |
| 选择器 | （无） |
| 清理 | 无 |

### ERR-003：HTTP 401 vs 业务 401

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 用错 Token 调 `/api/auth/admin` |
| 预期 | - HTTP 401，body `code: "invalid_admin_token"` |
| 选择器 | （无） |
| 清理 | 无 |

### ERR-004：HTTP 410 token_revoked

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_A` 已 revoke |
| 步骤 | 1. 调 `/api/public/coursewares/CW_RESTRICTED/access-check` 带 `TKN_A` 原值 |
| 预期 | - HTTP 410 `token_revoked` |
| 选择器 | （无） |
| 清理 | 重新生成 `TKN_A` |

### ERR-005：HTTP 422 last_token_required

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_LAST_TOKEN` 仅 `TKN_C` |
| 步骤 | 1. `DELETE /api/admin/tokens/TKN_C` |
| 预期 | - HTTP 422 `last_token_required` |
| 选择器 | （无） |
| 清理 | 无 |

---

## 4. 搜索结果与课件状态联动

### SR-001：课件删除后搜索不命中

| 项 | 内容 |
| ---- | ---- |
| 前置 | 临时课件 `CW_TEMP_DEL` 含 `临时` 标题 |
| 步骤 | 1. 删除 `CW_TEMP_DEL`<br>2. 调 `/api/public/coursewares/search?keyword=临时` |
| 预期 | - 命中数 = 0 |
| 选择器 | `p-result-empty-text` |
| 清理 | 无 |

### SR-002：受限课件更新描述后搜索可命中

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 描述改为含 `Java` 关键词 |
| 步骤 | 1. 调 `/api/public/coursewares/search?keyword=Java`<br>2. **不**应命中 `CW_RESTRICTED`（[02 §F01.04](../spec/02-功能需求.md)） |
| 预期 | - 命中数 = 0 |
| 选择器 | `p-result-empty-text` |
| 清理 | 无 |

### SR-003：标签删除后课件标签数更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_BASIC` 关联 2 个标签 |
| 步骤 | 1. 编辑课件移除 `TAG_INTRO`<br>2. 调 `/api/public/coursewares/search?keyword=入门` |
| 预期 | - 命中数 = 0（`CW_OPEN_BASIC` 不再带 `TAG_INTRO`） |
| 选择器 | `p-result-empty-text` |
| 清理 | 恢复标签 |

### SR-004：素材替换后课件预览更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_BASIC` 关联 `MAT_VIDEO_1` |
| 步骤 | 1. 编辑课件移除 `MAT_VIDEO_1` 并添加 `MAT_PDF_1`<br>2. 进入 P-DETAIL |
| 预期 | - 详情页素材区显示 PDF 链接 |
| 选择器 | `p-detail-material` |
| 清理 | 恢复 |

---

## 5. 数据完整性约束

### DI-001：分类非叶子节点不能挂课件

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 创建课件时选 `项目管理`（2 级分类） |
| 预期 | - HTTP 400 `courseware_category_not_leaf` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### DI-002：受 R-12 约束：最后一个 Token 不可换

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_LAST_TOKEN` 仅 `TKN_C` |
| 步骤 | 1. `POST /api/admin/tokens/TKN_C/regenerate` |
| 预期 | - HTTP 422 `last_token_required` |
| 选择器 | （无） |
| 清理 | 无 |

### DI-003：Token 删除级联解绑

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 关联 `TKN_A, TKN_B` |
| 步骤 | 1. `DELETE /api/admin/tokens/TKN_A`（前提：先清空 `CW_RESTRICTED` 的 `TKN_A`？不可以，因为这是 R-12 测试）<br>2. 实际场景：`CW_RESTRICTED` 必须有 ≥ 1 个 Token 才能继续<br>3. 先 `POST /api/admin/coursewares/CW_RESTRICTED` 编辑为 `accessTokenIds=[TKN_B, TKN_NEW]`<br>4. 再 `DELETE /api/admin/tokens/TKN_A` |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `courseware_token` 中 `CW_RESTRICTED` 关联 `TKN_A` 被解除 |
| 选择器 | （无） |
| 清理 | 恢复 |

### DI-004：素材删除级联解绑

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_BASIC` 关联 `MAT_VIDEO_1` |
| 步骤 | 1. 编辑课件移除 `MAT_VIDEO_1`<br>2. 删除 `MAT_VIDEO_1` |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `material_ids` 中 `MAT_VIDEO_1` 被清空 |
| 选择器 | （无） |
| 清理 | 恢复（重新 Setup） |

### DI-005：素材预览 PDF 同步清理

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PPT_1` 已转换（`preview_pdf_path` 非 NULL） |
| 步骤 | 1. `DELETE /api/admin/materials/{MAT_PPT_1}`（需先解绑全部课件）<br>2. 检查物理存储目录 |
| 预期 | - 200 `ok`<br>- 数据库 `preview_pdf_path` 被同步清空<br>- 物理目录中同名 `<safe_name>.pdf` 被删除（[04 §6.3](../spec/04-管理后台规格.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### DI-006：受限课件素材流被 ACL 拦截

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 受限且当前访问者未提供 Token |
| 步骤 | 1. 调 `GET /api/public/materials/{MAT_PPT_1}/stream`（不携带任何 Token）<br>2. 调 `GET /api/public/materials/{MAT_PPT_1}`（同上） |
| 预期 | - 流接口：401 / 403（与详情接口一致，[06 §2.1.1](../spec/06-非功能需求.md)）<br>- 单条接口：401 / 403 |
| 选择器 | （无） |
| 清理 | 无 |

---

## 6a. 集成验收（INT-V-001/002/003）

> 本节与 [08 §11a INT-V-001/002](../spec/08-验收标准.md) 一致，专为部署后跨服务集成验收设立。

### INT-V-001：PPT 上传触发 LibreOffice 转换

| 项 | 内容 |
| ---- | ---- |
| 前置 | 容器已安装 LibreOffice；admin 已登录 |
| 步骤 | 1. 上传 `courseware-with-pptx-20slides.pptx`<br>2. 后端响应中 `previewPdfPath` 非 NULL<br>3. 公开 `GET /api/public/materials/{id}/stream` |
| 预期 | - 200 + `Content-Type: application/pdf`<br>- `Content-Disposition: inline; filename="<name>.pdf"`<br>- 物理文件落在 `/app/storage/documents/<safe_name>.pdf`<br>- 与 [07 §6.1 素材上传数据流](../spec/07-技术架构.md) 描述一致 |
| 选择器 | （无，curl 验证） |
| 清理 | 删除该素材 |

### INT-V-002：PDF.js worker 静态资源可访问

| 项 | 内容 |
| ---- | ---- |
| 前置 | 前端已构建；nginx 已代理 `frontend/dist/` |
| 步骤 | 1. `curl -I http://localhost/pdf.worker.min.mjs`<br>2. 检查响应头与文件大小 |
| 预期 | - 200<br>- `Content-Type: application/javascript` 或 `text/javascript`<br>- 文件大小与 `frontend/dist/pdf.worker.min.mjs` 一致<br>- 与 [07 §2.2 PDF 渲染选型](../spec/07-技术架构.md) 一致 |
| 选择器 | （无） |
| 清理 | 无 |

### INT-V-003：前端产物含 viewer 子模块

| 项 | 内容 |
| ---- | ---- |
| 前置 | 前端已构建 |
| 步骤 | 1. `unzip -l frontend/dist/assets/*.js \| grep -i viewer` |
| 预期 | - 至少包含 `Viewer` / `VideoPlayer` / `PdfReader` / `SlideshowViewer` 4 个 chunk 路径<br>- 与 [03 §5a P-VIEWER](../spec/03-前台门户规格.md) 子组件清单一致 |
| 选择器 | （无） |
| 清理 | 无 |

---

## 6. 性能基线（N01 ~ N04）

> 执行环境：ECS 生产规格；客户端带宽 ≥ 50Mbps；本地 Chrome。

### N-001：首屏 Lighthouse Performance ≥ 80

| 项 | 内容 |
| ---- | ---- |
| 前置 | 缓存已冷 |
| 步骤 | 1. `lighthouse http://localhost --preset=desktop --only-categories=performance --output=json`<br>2. 取 `categories.performance.score * 100` |
| 预期 | - Performance 分数 ≥ 80（[08 §11 N-001](../spec/08-验收标准.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### N-002：AI 搜索接口 P95 ≤ 2s

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. `k6 run --vus 20 --duration 30s script-search.js`（脚本附后） |
| 预期 | - p95 ≤ 2000ms（[08 §11 N-002](../spec/08-验收标准.md)/[06 §1.1](../spec/06-非功能需求.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### N-003：后台保存接口 P95 ≤ 1s

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已登录后台 |
| 步骤 | 1. `k6 run --vus 10 --duration 30s script-admin-save.js`（创建 / 编辑 / 删除课件混合） |
| 预期 | - p95 ≤ 1000ms（[08 §11 N-003](../spec/08-验收标准.md)） |
| 选择器 | （无） |
| 清理 | 清理临时数据 |

### N-004：Token 校验接口 P95 ≤ 200ms

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. `k6 run script-unlock.js` |
| 预期 | - p95 ≤ 200ms（[08 §11 N-008](../spec/08-验收标准.md)，不含网络） |
| 选择器 | （无） |
| 清理 | 无 |

### N-005：k6 解锁脚本样例

```javascript
// script-unlock.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 20,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<200'],
  },
};

export default function () {
  const url = `${__ENV.BASE}/api/public/coursewares/${__ENV.CW}/unlock`;
  const res = http.post(url, JSON.stringify({ token: __ENV.TKN }), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```

> 运行：`k6 run -e BASE=https://... -e CW=CW_RESTRICTED -e TKN=... script-unlock.js`

---

## 7. 安全基线（N05 ~ N08）

### N-010：SQL 注入防御

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. `GET /api/public/coursewares/search?keyword=' OR 1=1 --` |
| 预期 | - HTTP 400 `search_query_invalid` 或 200 + 0 命中<br>- 无 500 错误<br>- 无数据库报错日志 |
| 选择器 | （无） |
| 清理 | 无 |

### N-011：XSS 防御

| 项 | 内容 |
| ---- | ---- |
| 前置 | 登录 |
| 步骤 | 1. 创建分类：`name=<script>alert(1)</script>` |
| 预期 | - HTTP 400 `category_name_invalid`<br>- 或输入被后端 sanitize |
| 选择器 | （无） |
| 清理 | 无 |

### N-012：Token 明文仅展示 1 次

| 项 | 内容 |
| ---- | ---- |
| 前置 | 新建 Token 后 |
| 步骤 | 1. 刷新 Token 详情（再次进入） |
| 预期 | - 数据库 `value_hash` 不可逆<br>- 接口 `/api/admin/tokens/:id` 不返回 `value` 字段 |
| 选择器 | （无） |
| 清理 | 无 |

### N-013：CORS 限制

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. `curl -H "Origin: https://evil.com" -i /api/public/coursewares` |
| 预期 | - 无 `Access-Control-Allow-Origin: https://evil.com`<br>- 仅白名单 origin（[07 §N05](../spec/07-技术架构.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### N-014：Admin Token 限流

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 60 秒内尝试登录 10 次错误 Token |
| 预期 | - 后续请求 429 `rate_limited` |
| 选择器 | （无） |
| 清理 | 等待 |

### N-006a：生产环境强制 HTTPS

| 项 | 内容 |
| ---- | ---- |
| 前置 | 部署在 ECS（`https://learning-hub.smartmoves.com.cn`） |
| 步骤 | 1. `curl -kI https://learning-hub.smartmoves.com.cn/`<br>2. `curl -I http://learning-hub.smartmoves.com.cn/`（强制 HTTP） |
| 预期 | - 步骤 1：返回 200，证书有效（[08 §11 N-006](../spec/08-验收标准.md)）<br>- 步骤 2：服务端 301/302 重定向到 `https://...`（HSTS / 统一重定向规则）<br>- 严格模式下返回 403 拒接明文流量<br>- 本地 `http://localhost` 不受此约束（开发环境） |
| 选择器 | （无） |
| 清理 | 无 |

---

## 8. 兼容性（N09）

### N-020：Chrome 桌面端

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 跑 F-001 ~ F-046 全部用例 |
| 预期 | - 100% 通过 |
| 选择器 | （无） |
| 清理 | 无 |

### N-021：Edge 桌面端

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 跑关键用例 F-001, F-010, F-030, A-001, A-110 |
| 预期 | - 全部通过 |
| 选择器 | （无） |
| 清理 | 无 |

### N-022：移动端浏览器（v1.1+）

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. iOS Safari / Android Chrome 跑 F-001 ~ F-040 |
| 预期 | - 关键路径通过；差异仅样式 |
| 选择器 | （无） |
| 清理 | 无 |

### N-023：键盘可达性

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 在 P-HOME 通过 Tab → Enter 完成搜索 |
| 预期 | - Tab 顺序合理<br>- 焦点可见 |
| 选择器 | `:focus-visible` |
| 清理 | 无 |

---

## 9. 监控与日志（N10）

### N-030：关键指标可见

| 项 | 内容 |
| ---- | ---- |
| 前置 | 部署 Prometheus + Grafana |
| 步骤 | 1. `curl /actuator/metrics` 或 `curl /metrics`（取决于实现） |
| 预期 | - 至少包含：`http_server_requests_seconds_*`, `jvm_memory_*`, `ai_search_latency_*`（[06 §10](../spec/06-非功能需求.md)） |
| 选择器 | （无） |
| 清理 | 无 |

### N-031：日志结构化

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 触发一次登录<br>2. `docker logs learning-hub` |
| 预期 | - 单条 JSON：含 `ts`, `level`, `requestId`, `userId`, `action`, `durationMs` |
| 选择器 | （无） |
| 清理 | 无 |

### N-032：告警触发

| 项 | 内容 |
| ---- | ---- |
| 前置 | Alertmanager 已配置 |
| 步骤 | 1. 制造 5xx 错误率 > 5% 持续 5 分钟 |
| 预期 | - 收到告警通知 |
| 选择器 | （无） |
| 清理 | 无 |

---

## 10. 数据迁移与备份

### N-040：数据库备份恢复

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已执行 `pg_dump` |
| 步骤 | 1. `psql -U hub -d hub < backup.sql`<br>2. 重启服务 |
| 预期 | - 全部数据回滚到 dump 时刻<br>- 服务正常启动 |
| 选择器 | （无） |
| 清理 | 无 |

### N-041：素材文件恢复

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已 tar 打包 `/app/storage/documents` |
| 步骤 | 1. `tar -xf documents.tar.gz -C /app/storage/`<br>2. 重启服务 |
| 预期 | - 全部素材文件可访问 |
| 选择器 | （无） |
| 清理 | 无 |

---

## 11. 跨模块一致性矩阵

| 触发 | 联动模块 | 用例 |
| ---- | -------- | ---- |
| 课件删除 | Token 关联数、素材不联动 | A-133, A-134, X-010 |
| 分类删除 | 课件归属校验 | C-008, X-011 |
| 素材删除 | 课件引用清理 | M-008, X-012 |
| 标签删除 | 课件标签清理 | T-007, X-013 |
| Token 失效 | 前台 localStorage 清理 | FTK-003 |
| Token 删除/重生（最后） | 课件降级或拒绝 | A-127, TKN-006, TKN-008 |

---

## 12. 用例覆盖矩阵

| 文档章节 | 用例 ID |
| -------- | ------- |
| [02 §F06 受限课件](../spec/02-功能需求.md) | FTK-001 ~ FTK-007 |
| [06 §1 性能](../spec/06-非功能需求.md) | N-001 ~ N-005 |
| [06 §2 安全](../spec/06-非功能需求.md) | N-006a, N-010 ~ N-014 |
| [06 §4 兼容](../spec/06-非功能需求.md) | N-020 ~ N-023 |
| [06 §10 监控](../spec/06-非功能需求.md) | N-030 ~ N-032 |
| [08 N-001~N-009](../spec/08-验收标准.md) | N-001 ~ N-005, N-006a, N-008 (N-004 复盖) |
| [07 §5 安全](../spec/07-技术架构.md) | N-013, N-014 |
| [05 §R-12](../spec/05-数据模型.md) | DI-002, A-127, TKN-006, TKN-008 |
| [08 §11a INT-V-001/002](../spec/08-验收标准.md) | INT-V-001, INT-V-002, INT-V-003 |
| [04 §6.3 删除素材清理](../spec/04-管理后台规格.md) | DI-005 |
| [10 §5.2.4 限流与 ACL](../spec/10-API设计规范.md) | DI-006 |
