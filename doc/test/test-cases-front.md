# 前台门户测试用例（F-*）

> 适用范围：[03-前台门户规格](../spec/03-前台门户规格.md) / [02-功能需求 F01](../spec/02-功能需求.md)。
> 入口：`BASE`（[test-data §1](./test-data.md)）。
> 数据前置：完成 [setup-teardown.md §3](./setup-teardown.md) 全部 Setup 步骤。

---

## 1. 公共约定

| 项 | 约定 |
| ---- | ---- |
| 用例 ID 格式 | `F-NNN` |
| 前置 | 浏览器已登录后台，localStorage 已清空（仅鉴权用例需登出） |
| 步骤描述 | 用祈使语气；不写伪代码 |
| 断言写法 | `expect(<selector>).<matcher>(<value>)` |
| 失败处理 | 自动截图 + 记录 network / storage（见 [setup-teardown §5.3](./setup-teardown.md)） |

---

## 2. 首页空态（P-HOME）

### F-001：访问首页加载

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 打开 `{BASE}` |
| 预期 | - URL 命中 `/`<br>- `[data-testid="p-home-title"]` 可见<br>- `[data-testid="p-home-search-input"]` 可见且可输入<br>- 顶部有 `Learning Hub` 品牌标识<br>- 无 `g-toast--error` 出现 |
| 选择器 | `p-home-title`, `p-home-search-input` |
| 清理 | 无 |

### F-002：首页空态点击搜索按钮无输入

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-001 |
| 步骤 | 1. 不输入任何字符<br>2. 点击 `[data-testid="p-home-search-btn"]` |
| 预期 | - 按钮 disabled / 点击不触发搜索请求<br>- 若有 hover 提示"请输入搜索关键词"，可见 |
| 选择器 | `p-home-search-btn` |
| 清理 | 无 |

### F-002a：搜索框 placeholder 文本

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-001 |
| 步骤 | 1. 观察 `[data-testid="p-home-search-input"]` 的 `placeholder` 属性 |
| 预期 | - 文案为 `请帮找一下项目管理相关的课程`（[08 §2 F-002](../spec/08-验收标准.md)）<br>- 不会随页面状态变化<br>- 多语言场景下优先取 `Accept-Language: zh-CN` 响应 |
| 选择器 | `p-home-search-input` |
| 清理 | 无 |

### F-003：首页直接输入搜索并跳转

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-001 |
| 步骤 | 1. `[data-testid="p-home-search-input"]` 输入 `项目管理`<br>2. 点击 `[data-testid="p-home-search-btn"]` |
| 预期 | - 跳转到 `/result?q=项目管理`（或 `?keyword=项目管理`）<br>- `[data-testid="p-result-count"]` 显示 `找到 N 个课件`（N ≥ 1）<br>- 至少包含 1 张 `[data-testid="p-result-card"]` |
| 选择器 | `p-result-count`, `p-result-card` |
| 清理 | 清空搜索框 |

### F-005：搜索加载态

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-001 |
| 步骤 | 1. `[data-testid="p-home-search-input"]` 输入 `Java`<br>2. 点击搜索后**立即**在 `page.waitForResponse` 之前观察中间态 |
| 预期 | - 出现 `[data-testid="p-result-loading"]`，文本为 `⏳ AI 搜索中，请稍候…`（[08 §2 F-005](../spec/08-验收标准.md)）<br>- 加载态持续 ≥ 200ms（依赖接口响应）<br>- 接口返回后加载态被结果列表替换 |
| 选择器 | `p-result-loading` |
| 清理 | 无 |

## 3. 搜索结果页（P-RESULT）

> **v1.1 起**：AI 智能搜索返回 `data.source` 字段，徽标逻辑跟随 `source` 动态切换：
> - `source="llm"` → 「AI 智能搜索」（qwen-plus NL2SQL 命中）
> - `source="keyword"` → 「AI 智能搜索 · 降级中」（ILIKE 兜底）
> 所有用例必须同时验证 `data.source` + 徽标文案两项。

### F-007：自然语言长句命中（LLM 路径）

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成；后端注入有效 `DASHSCOPE_API_KEY` 且能调用阿里云百炼 |
| 步骤 | 1. 后台创建标题含 `增量绩效-{ts}` 的开放课件（`access_mode=open`）<br>2. 打开 `{BASE}/?q=帮我找一下与增量绩效-{ts}相关的课件`<br>3. 等待网络空闲 |
| 预期 | - 接口 `/api/public/coursewares/search` 返回 `data.source == "llm"`<br>- 徽标为「AI 智能搜索」（不含「降级中」）<br>- 命中包含刚才创建的课件，`data-courseware-id` 与新建 ID 一致 |
| 选择器 | `p-result-card[data-courseware-id="<新建 ID>"]`, `[data-testid="p-result-badge-llm"]`（如页面渲染该标识） |
| 清理 | 删除新建的课件 |
| e2e | [front-search-llm.spec.ts F-007](../../frontend/e2e/front-search-llm.spec.ts) |

### F-008：无 DASHSCOPE_API_KEY 时降级

| 项 | 内容 |
| ---- | ---- |
| 前置 | e2e 环境**未**注入 `DASHSCOPE_API_KEY`；后端以空 key 启动 |
| 步骤 | 1. 打开 `{BASE}/?q=帮我找一下与增量绩效相关的课件`（长句）<br>2. 等待网络空闲 |
| 预期 | - 接口 `/api/public/coursewares/search` 返回 `data.source == "keyword"`<br>- 徽标显示「AI 智能搜索 · 降级中」（`source-keyword` 徽标逻辑触发）<br>- 如 DB 中存在含「增量绩效」的课件，仍能以 ILIKE 命中（0 命中时也返回 `source="keyword"`，不返回 5xx） |
| 选择器 | `source-keyword`, `[data-testid="p-result-badge-keyword"]`（如页面渲染） |
| 清理 | 无 |
| e2e | [front-search-llm.spec.ts F-008](../../frontend/e2e/front-search-llm.spec.ts) |

### F-009：短关键词仍按 ILIKE 命中（与 LLM 路径结果一致）

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成；DB 中存在标题含「项目管理」的课件 |
| 步骤 | 1. 打开 `{BASE}/?q=管理`<br>2. 等待网络空闲 |
| 预期 | - 命中包含「项目管理」相关课件<br>- `data.source` 在不同环境可能为 `"llm"`（LLM 召回）或 `"keyword"`（降级），两者徽标文案不同但命中集合一致<br>- 短关键词场景下 LLM 路径与 ILIKE 路径的召回重合度高（验收重点） |
| 选择器 | `p-result-card[data-courseware-id]`, `p-result-count` |
| 清理 | 无 |
| e2e | [front-search-llm.spec.ts F-009](../../frontend/e2e/front-search-llm.spec.ts) |

> **依据**：[10 §5.1.3 v1.1 LLM-to-SQL 实现说明](../spec/10-API设计规范.md)、[07 §2.4 AI 能力](../spec/07-技术架构.md)、[deploy/README §7.9](../../deploy/README.md)。

### F-010：搜索命中开放课件

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 |
| 步骤 | 1. 打开 `{BASE}/result?q=项目管理`<br>2. 等待网络空闲 |
| 预期 | - 命中 ≥ 1 条，且为 `CW_OPEN_BASIC`（`项目管理入门`）<br>- 卡片无 🔒 图标（即无 `p-result-card-lock`）<br>- 卡片 `data-access-mode="open"` |
| 选择器 | `p-result-card[data-courseware-id="CW_OPEN_BASIC"]` |
| 清理 | 无 |

### F-011：受限课件以锁形标识出现在搜索结果

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 |
| 步骤 | 1. 打开 `{BASE}/result?q=Java`<br>2. 等待网络空闲 |
| 预期 | - 结果**包含** `CW_RESTRICTED`<br>- 该卡片 `data-access-mode="restricted"`<br>- 包含 `[data-testid="p-result-card-lock"]`（🔒 + `aria-label="该课件需要访问令牌"`） |
| 选择器 | `p-result-card[data-courseware-id="CW_RESTRICTED"]`, `p-result-card-lock` |
| 清理 | 无 |

> 依据：[02 §F01.05](../spec/02-功能需求.md) / [08 FTK-001](../spec/08-验收标准.md) / [03 §3.5](../spec/03-前台门户规格.md)。**受限课件可见且带锁形标识**，点击后依据本地记忆决定 P-LOCKED 或 P-DETAIL。

### F-012：搜索命中数量显示

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 |
| 步骤 | 1. 观察 `[data-testid="p-result-count"]` |
| 预期 | - 文案形如 `找到 2 个课件`（`项目管理入门` + `Scrum 实践指南`，两者都带 `TAG_PM`） |
| 选择器 | `p-result-count` |
| 清理 | 无 |

### F-013：搜索空结果空态

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 打开 `{BASE}/result?q=不存在的关键词XYZ` |
| 预期 | - `[data-testid="p-result-empty-icon"]` 可见<br>- `[data-testid="p-result-empty-text"]` 文案含"没有找到相关课件"<br>- 0 张 `p-result-card` |
| 选择器 | `p-result-empty-icon`, `p-result-empty-text`, `p-result-card` |
| 清理 | 无 |

### F-014：搜索关键词为空被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 直接打开 `{BASE}/result?q=`（无值） |
| 预期 | - 触发 `search_query_empty` 错误码<br>- 停留在 P-RESULT 或弹错误提示<br>- 后端日志记 400 |
| 选择器 | `p-result-empty-text` 或 `g-toast--error` |
| 清理 | 无 |

### F-015：搜索关键词超过 200 字符

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 在搜索框输入 201 个字符<br>2. 提交搜索 |
| 预期 | - 触发 `search_query_too_long` 错误码<br>- 前端拦截在 200 字符以内（input 限长）或后端返回 400 |
| 选择器 | `p-home-search-input`, `g-toast--error` |
| 清理 | 清空搜索框 |

### F-016：结果页直接输入再搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. `[data-testid="p-result-search-input"]` 输入 `Scrum`<br>2. 回车 / 点击搜索图标 |
| 预期 | - URL 同步更新为 `?q=Scrum`<br>- 命中 `CW_OPEN_MULTI`<br>- 旧 `项目管理` 课件不在结果中 |
| 选择器 | `p-result-search-input`, `p-result-card` |
| 清理 | 无 |

### F-017：清空全部按钮（v1.0 仅控制台日志）

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. 点击 `[data-testid="p-result-clear-btn"]`（若 v1.0 隐藏则跳过） |
| 预期 | - 至少 console 有 `[Analytics] clear_all` 日志<br>- UI 行为：清空结果并显示空态 |
| 选择器 | `p-result-clear-btn`, `p-result-empty-text` |
| 清理 | 无 |

### F-018：AI 智能搜索标签可见

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. 观察顶部徽标 |
| 预期 | - `[data-testid="p-result-ai-badge"]` 可见<br>- 文本含"AI 智能搜索" |
| 选择器 | `p-result-ai-badge` |
| 清理 | 无 |

### F-019：结果页分页（多页结果）

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 后再创建 ≥ 11 个标题含 `课程` 的开放课件（v1.1+） |
| 步骤 | 1. 打开 `{BASE}/result?q=课程&page=1&size=10`<br>2. 切换至 page=2 |
| 预期 | - page=1 渲染 10 张卡片<br>- page=2 渲染剩余卡片（≥ 1 张）<br>- 分页组件 `[data-testid="p-result-pagination"]` 可见 |
| 选择器 | `p-result-card`, `p-result-pagination` |
| 清理 | 删除用于分页的临时课件 |

> v1.0 单页 size = 10；本用例为兼容性预留，需在 setup 后通过临时数据完成。

### F-019a：结果页顶部 Logo 跳回首页空态

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面（结果页） |
| 步骤 | 1. 点击顶部 `[data-testid="p-result-logo"]`（文字 `Learning Hub`） |
| 预期 | - URL 变为 `{BASE}/`（P-HOME）<br>- 渲染首页空态：`[data-testid="p-home-title"]` 可见<br>- 搜索框为初始空值（不保留上次的 `q=项目管理`） |
| 选择器 | `p-result-logo`, `p-home-title`, `p-home-search-input` |
| 清理 | 无 |

> 依据：[08 §2 F-007](../spec/08-验收标准.md) / [03 §2.6](../spec/03-前台门户规格.md)。**结果页 Logo = 顶导统一 Logo**，与详情页 F-044 共用同一组件。

### F-020：响应式：移动端结果页

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. `page.setViewportSize({ width: 375, height: 667 })`<br>2. 重新加载 |
| 预期 | - 单列布局，卡片宽度自适应<br>- 无横向滚动<br>- 顶部 Logo 与搜索输入可折叠为汉堡菜单（如有） |
| 选择器 | `p-result-card` |
| 清理 | 恢复视口 `1440x900` |

---

## 4. 受限课件锁定页（P-LOCKED）

### F-030：受限课件被锁定（无 Token 时）

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成；localStorage 干净（`coursewareTokens = {}`） |
| 步骤 | 1. 打开 `{BASE}/detail/CW_RESTRICTED`（受限课件详情 URL）<br>2. 等待前端通过 `/api/public/coursewares/CW_RESTRICTED/access-check` 判定 |
| 预期 | - 命中锁定页 P-LOCKED<br>- `[data-testid="p-locked-title"]` 文本为 `Java 后端工程实践`<br>- `[data-testid="p-locked-token-input"]` 可见<br>- `[data-testid="p-locked-unlock-btn"]` 可见且初始 disabled |
| 选择器 | `p-locked-title`, `p-locked-token-input`, `p-locked-unlock-btn` |
| 清理 | 无 |

### F-031：受限课件直接打开解锁页面（含 Token 时自动通过）

| 项 | 内容 |
| ---- | ---- |
| 前置 | localStorage `coursewareTokens` 包含 `CW_RESTRICTED -> TKN_A 明文` |
| 步骤 | 1. 打开 `{BASE}/detail/CW_RESTRICTED` |
| 预期 | - 自动通过校验并渲染 P-DETAIL<br>- 不出现 P-LOCKED |
| 选择器 | `p-detail-title` |
| 清理 | 清空 localStorage `coursewareTokens` |

### F-032：锁定页输入有效 Token 解锁

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. `[data-testid="p-locked-token-input"]` 输入 `TKN_A` 原值（`AB12CD34EF56GH78IJ90KL34`）<br>2. 点击 `[data-testid="p-locked-unlock-btn"]` |
| 预期 | - HTTP 200，`code: "ok"`<br>- 跳转至 P-DETAIL<br>- `localStorage.coursewareTokens` 出现 `CW_RESTRICTED -> AB12CD34EF56GH78IJ90KL34` |
| 选择器 | `p-locked-token-input`, `p-locked-unlock-btn`, `p-detail-title` |
| 清理 | 清空 `coursewareTokens` |

### F-033：锁定页输入无效 Token 提示

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. 输入 `INVALID-12345`<br>2. 点击解锁 |
| 预期 | - HTTP 401，`code: "invalid_token"`<br>- `[data-testid="p-locked-error"]` 文案含"令牌无效，请检查后重试"<br>- 仍在锁定页，输入框保留原值 |
| 选择器 | `p-locked-error` |
| 清理 | 清空输入框 |

### F-034：锁定页输入已失效 Token 提示并清空记忆

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_A` 在 Setup 后**额外**调用过 `POST /api/admin/tokens/TKN_A/revoke` |
| 步骤 | 1. localStorage 中写入 `coursewareTokens[CW_RESTRICTED] = TKN_A 原值`<br>2. 打开 `{BASE}/detail/CW_RESTRICTED` |
| 预期 | - 前端调 `/access-check` 返回 410 `token_revoked`<br>- 仍渲染 P-LOCKED<br>- `[data-testid="p-locked-error"]` 含"令牌已失效，请重新输入"<br>- localStorage 中该 key 被移除 |
| 选择器 | `p-locked-error` |
| 清理 | 重新生成 `TKN_A`（不删） |

### F-035：锁定页输入格式非法

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. 输入 `ab`（长度 < 16）<br>2. 点击解锁 |
| 预期 | - HTTP 400，`code: "invalid_token_format"`<br>- 错误文案含"令牌长度非法" |
| 选择器 | `p-locked-error` |
| 清理 | 清空输入框 |

### F-036：锁定页返回搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. 点击 `[data-testid="p-locked-back-btn"]` |
| 预期 | - 返回上一页面（`/result?q=...` 或 `/`）<br>- 不提交任何请求 |
| 选择器 | `p-locked-back-btn` |
| 清理 | 无 |

### F-037：锁定页输入超长 Token 拦截

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. 输入长度 65 的字符串（如 `a` × 65）<br>2. 点击解锁 |
| 预期 | - 前端提交前拦截：input `maxlength=64` 或按钮 disabled<br>- 或后端 400 `invalid_token_format`（[10 §2.4](../spec/10-API设计规范.md)）<br>- 错误文案含"令牌长度非法"（[08 §9 FTK-007](../spec/08-验收标准.md)）<br>- 不发出 `/unlock` 请求 |
| 选择器 | `p-locked-token-input`, `p-locked-unlock-btn`, `p-locked-error` |
| 清理 | 清空输入框 |

### F-038：受限课件 5 次错误限流

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-030 |
| 步骤 | 1. 连续 5 次输入错误 Token 并点击解锁 |
| 预期 | - 第 6 次起 HTTP 429 `rate_limited`<br>- 错误文案含"解锁失败，请稍后重试"（[10 §3.2.6](../spec/10-API设计规范.md)） |
| 选择器 | `p-locked-error` |
| 清理 | 等待 1 分钟后清空错误计数 |

---

## 5. 课件详情页（P-DETAIL）

### F-040：详情页字段正确

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-032 通过解锁进入 P-DETAIL |
| 步骤 | 1. 观察页面 |
| 预期 | - 标题 = `Java 后端工程实践`<br>- 作者 = `李四`<br>- 分类路径 = `软件工程 / 后端 / Java`<br>- 标签 = [`后端`]<br>- 描述 = `面向 Java 后端工程师的进阶培训材料。`<br>- 素材 = 1 项（`java-backend.pptx`） |
| 选择器 | `p-detail-title`, `p-detail-author`, `p-detail-category-path`, `p-detail-tags`, `p-detail-description`, `p-detail-material` |
| 清理 | 无 |

### F-041：详情页视频播放

| 项 | 内容 |
| ---- | ---- |
| 前置 | 通过搜索进入 `CW_OPEN_BASIC` 详情 |
| 步骤 | 1. 点击 `[data-testid="p-detail-video"]`<br>2. 等待 1 秒 |
| 预期 | - 视频元素处于播放 / 加载状态<br>- 无 404 / 403 报错 |
| 选择器 | `p-detail-video` |
| 清理 | 暂停视频 |

### F-042：[已废弃]详情页 PDF 链接可访问（v1.2 起前台不提供下载入口）

| 项 | 内容 |
| ---- | ---- |
| 前置 | v1.1 及之前：`CW_OPEN_MULTI` 已关联 PDF 素材（`MAT_PDF_1`） |
| 步骤 | 1. ~~找到 `[data-testid="p-detail-pdf-link"]` 并点击 / 复制 href~~ |
| 预期 | - v1.2 起：**[data-testid="p-detail-pdf-link"] 不存在**；P-DETAIL 不再提供任何 PDF 预览 / 下载链接<br>- 仍可点击“在线浏览”进入 P-VIEWER-PDF 以阅读 |
| 选择器 | `p-detail-pdf-link`（断言 toHaveCount(0)） |
| 清理 | 无 |

### F-043：详情页返回搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-040 |
| 步骤 | 1. 点击 `[data-testid="p-detail-back-btn"]` |
| 预期 | - 返回上一页面<br>- 之前的 P-RESULT 搜索状态保留（关键词、页码） |
| 选择器 | `p-detail-back-btn` |
| 清理 | 无 |

### F-044：详情页 Logo 跳转首页

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-040 |
| 步骤 | 1. 点击 `[data-testid="p-detail-logo"]` |
| 预期 | - 跳转到 `{BASE}/`（P-HOME） |
| 选择器 | `p-detail-logo` |
| 清理 | 无 |

### F-045：开放课件免 Token 直达详情

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 打开 `{BASE}/detail/CW_OPEN_BASIC` |
| 预期 | - 直接渲染 P-DETAIL<br>- 不出现 P-LOCKED<br>- 无 `p-locked-*` 元素 |
| 选择器 | `p-detail-title` |
| 清理 | 无 |

### F-046：详情页多素材列表渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | 进入 `CW_OPEN_MULTI` 详情（2 个素材） |
| 步骤 | 1. 列出 `[data-testid="p-detail-material"]` 全部项 |
| 预期 | - 2 项<br>- `data-material-type` 分别 = `VIDEO`, `PDF` |
| 选择器 | `p-detail-material` |
| 清理 | 无 |

### F-047：详情页素材按钮文案为"在线浏览"且无下载入口

| 项 | 内容 |
| ---- | ---- |
| 前置 | 进入 `CW_OPEN_BASIC` 或 `CW_OPEN_MULTI` 详情页 |
| 步骤 | 1. 查找素材项中 `[data-testid="p-detail-material-browse-btn"]`<br>2. 同时确认该素材块**不再提供** `[data-testid="p-detail-material-download-link"]` |
| 预期 | - `p-detail-material-browse-btn` 文案为 `在线浏览`<br>- v1.2 起：同一素材块**不存在** `p-detail-material-download-link`；页面中**不出现** `下载到本地` 链接 / 文字<br>- 唯一可访问素材文件的方式是点击"在线浏览"进入 P-VIEWER |
| 选择器 | `p-detail-material-browse-btn`, `p-detail-material-download-link`（断言 toHaveCount(0)） |
| 清理 | 无 |

> 依据：[02 F01.08](../spec/02-功能需求.md) / [08 §8a AC-019~021](../spec/08-验收标准.md) / [03 §5.4](../spec/03-前台门户规格.md) / [09 §6.3](../spec/09-UI规格.md)。v1.2 起 P-DETAIL 同步去除了原“下载到本地”文字链接。

---

## 5a. 素材在线浏览页（P-VIEWER）

### F-048：P-VIEWER-VIDEO 视频行内播放

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_BASIC` 已关联 MP4 素材（`MAT_VIDEO_1`），`preview_pdf_path = NULL` |
| 步骤 | 1. 进入详情 → 点击该素材项的 `[data-testid="p-detail-material-browse-btn"]`<br>2. URL 变为 `/?view=viewer&id=<materialId>&cw=<coursewareId>`<br>3. 等待 `[data-testid="p-viewer-video"]` 可见且 `readyState > 0` |
| 预期 | - `[data-testid="p-viewer-video"]` 可见，内嵌 `<video controls>` 元素 `readyState > 0`<br>- `[data-testid="p-viewer-video-info-name"]` 为原文件名<br>- `[data-testid="p-viewer-video-info-duration"]` 为 `mm:ss` 格式（如 `01:23`）<br>- `[data-testid="p-viewer-video-info-size"]` 为人类可读大小（如 `12.34 MB`）<br>- **页面不存在** `[data-testid="p-viewer-download-link"]`（v1.2 起 P-VIEWER 隐藏所有下载入口）<br>- 顶栏 / 信息面板中**不出现**文字 `下载到本地` |
| 选择器 | `p-viewer-video`, `p-viewer-video-info`, `p-viewer-video-info-name`, `p-viewer-video-info-duration`, `p-viewer-video-info-size` |
| 清理 | 无 |

### F-049：P-VIEWER-PDF PDF Word 式阅读

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_MULTI` 已关联 PDF 素材（`MAT_PDF_1`） |
| 步骤 | 1. 进入详情 → 点击该 PDF 素材的 `p-detail-material-browse-btn`<br>2. 等待 `[data-testid="p-viewer-pdf"]` 可见<br>3. 滚动容器至 50% 位置<br>4. 观察 `[data-testid="p-viewer-pdf-page-indicator"]` |
| 预期 | - `[data-testid="p-viewer-pdf"]` 可见<br>- 页面连续滚动渲染<br>- 滚动后页码气泡同步更新为当前可见页（如 `第 3 / 10 页`）<br>- 页码气泡 `aria-live="polite"`（无障碍读取）<br>- 顶栏含 `p-viewer-pdf-toolbar` 与 `p-viewer-pdf-zoom-in` / `p-viewer-pdf-zoom-out` / `p-viewer-pdf-zoom-label` |
| 选择器 | `p-viewer-pdf`, `p-viewer-pdf-toolbar`, `p-viewer-pdf-zoom-in`, `p-viewer-pdf-zoom-out`, `p-viewer-pdf-zoom-label`, `p-viewer-pdf-page-indicator` |
| 清理 | 无 |

### F-050：P-VIEWER-PPT 幻灯片样式

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 已关联 20 页 PPTX 素材（`MAT_PPTX_20`），LibreOffice 已生成 `preview_pdf_path` |
| 步骤 | 1. 解锁进入详情 → 点击该 PPT 素材的 `p-detail-material-browse-btn`<br>2. 等待 `[data-testid="p-viewer-ppt"]` 可见<br>3. 检查 `[data-testid="p-viewer-ppt-indicator"]` 初始文本<br>4. 点 `[data-testid="p-viewer-ppt-next"]`<br>5. 按 `ArrowRight`<br>6. 点 `[data-testid="p-viewer-ppt-prev"]`（两次回到首页）<br>7. 检查末页状态 |
| 预期 | - 初始指示器为 `1 / 20`<br>- 点 `下一张` 后为 `2 / 20`<br>- 按 `ArrowRight` 后为 `3 / 20`<br>- 点两次 `上一张` 后回到 `1 / 20`，此时 `p-viewer-ppt-prev` `disabled` 且文案变 `已是第一张`<br>- 点 `下一张` 到第 20 页时 `p-viewer-ppt-next` `disabled` 且文案变 `已是最后一张`<br>- `[data-testid="p-viewer-ppt-canvas"]` 在每页均能成功绘制（`width/height > 0`） |
| 选择器 | `p-viewer-ppt`, `p-viewer-ppt-canvas`, `p-viewer-ppt-prev`, `p-viewer-ppt-next`, `p-viewer-ppt-indicator` |
| 清理 | 无 |

> CI 环境若无 LibreOffice：使用预生成的 20 页 PPTX + 手动的 preview PDF fixture 跳过 `M-009`、仅验证 UI 状态机。

### F-051：P-VIEWER 返回 P-DETAIL

| 项 | 内容 |
| ---- | ---- |
| 前置 | 分别从 F-048 / F-049 / F-050 任一样式进入 P-VIEWER |
| 步骤 | 1. 点击顶栏 `[data-testid="p-viewer-back-btn"]` |
| 预期 | - URL 变化为 `/?view=detail&id=<coursewareId>` 或等价 detail 状态<br>- P-DETAIL 重新渲染，`p-detail-title` 可见 |
| 选择器 | `p-viewer-back-btn`, `p-detail-title` |
| 清理 | 无 |

### F-052：P-VIEWER 不提供任何下载入口（v1.2）

| 项 | 内容 |
| ---- | ---- |
| 前置 | 任一 P-VIEWER 样式（VIDEO / PDF / PPT）；以 VIDEO 为例验证三种样式均无下载 |
| 步骤 | 1. 进入 VIDEO / PDF / PPT 任一样式的 P-VIEWER<br>2. 抓取页面内全部 `<a>` / `<button>` 元素，匹配 href 或文本包含 `下载` / `下载到本地` / `/api/public/materials/` / `download` 的命中集合<br>3. 同时断言 `[data-testid="p-viewer-download-link"]` **不存在** |
| 预期 | - 三种 P-VIEWER 样式均**不存在** `[data-testid="p-viewer-download-link"]`<br>- 顶栏 / 工具栏 / 信息面板 / 错误态 / 空态中**不出现** `下载到本地` 文本链接<br>- 唯一例外是浏览器原生 `<video controls>` 自带的下载按钮（任务范围不覆盖原生 UI）<br>- v1.2 起：P-DETAIL 的 `[data-testid="p-detail-material-download-link"]` 同样**不存在**；前台整体**不提供**任何素材下载入口 |
| 选择器 | `p-viewer-download-link`（断言 toHaveCount(0)）、`page.locator('a:has-text("下载到本地")')`（仅 P-VIEWER 范围） |
| 清理 | 无 |

### F-053：P-VIEWER-PPT 全屏切换

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-050 通过 |
| 步骤 | 1. 点击 `[data-testid="p-viewer-ppt-fullscreen"]`<br>2. 检查 `document.fullscreenElement` |
| 预期 | - `document.fullscreenElement` 不为空且指向 `[data-testid="p-viewer-ppt-canvas"]`<br>- 再次点击按钮退出全屏后 `document.fullscreenElement === null` |
| 选择器 | `p-viewer-ppt-fullscreen`, `p-viewer-ppt-canvas` |
| 清理 | `document.exitFullscreen()` |

### F-054：P-VIEWER-PDF 缩放

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-049 通过 |
| 步骤 | 1. 连续点击 3 次 `[data-testid="p-viewer-pdf-zoom-in"]`<br>2. 观察 `[data-testid="p-viewer-pdf-zoom-label"]` |
| 预期 | - 默认 `125%`(参见 [03 §5a.3](./../spec/03-前台门户规格.md) `scale = 1.25`)<br>- 连续点 zoom-in:`125% → 150% → 200%`(第三次点击因已到上限 `disabled`,文案不再变化)<br>- 页面宽度同步增加<br>- 点 `p-viewer-pdf-zoom-out` 可回落:`200% → 150% → 125% → 100% → 75%` |
| 选择器 | `p-viewer-pdf-zoom-in`, `p-viewer-pdf-zoom-out`, `p-viewer-pdf-zoom-label` |
| 清理 | 无 |

### F-055：P-VIEWER 顶栏 Logo 回首页空态

| 项 | 内容 |
| ---- | ---- |
| 前置 | 任一 P-VIEWER 样式 |
| 步骤 | 1. 点击顶栏 `[data-testid="p-viewer-logo"]` |
| 预期 | - URL 变为 `{BASE}/`（P-HOME）<br>- 搜索框为空值 |
| 选择器 | `p-viewer-logo`, `p-home-title` |
| 清理 | 无 |

### F-056：P-VIEWER-PPT 预览未生成兜底

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PPTX_PENDING` 上传后未等待 LibreOffice 转换完成（`preview_pdf_path = NULL`） |
| 步骤 | 1. 进入该素材的 P-VIEWER |
| 预期 | - `[data-testid="p-viewer-ppt-preview-pending"]` 提示 `预览尚未生成，请稍后重试`（v1.2 起不再带“下载到本地查看”）<br>- 页面**不存在** `[data-testid="p-viewer-download-link"]`；顶栏 / 空态中**不出现** `下载到本地` 链接<br>- v1.2 起：P-DETAIL 也不提供 `p-detail-material-download-link` 下载入口；如需离线查看请等待预览生成后再访问 |
| 选择器 | `p-viewer-ppt-preview-pending`, `p-viewer-download-link`（断言 toHaveCount(0)） |
| 清理 | 无 |

---

## 6. 通用错误页

### F-050：访问不存在课件

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 打开 `{BASE}/detail/不存在ID9999` |
| 预期 | - HTTP 404 `courseware_not_found`<br>- 渲染通用错误页：[`通用错误页 §11`](../spec/03-前台门户规格.md) |
| 选择器 | `g-error-page`（前端约定） |
| 清理 | 无 |

### F-051：5xx 错误页

| 项 | 内容 |
| ---- | ---- |
| 前置 | 临时停掉后端服务 |
| 步骤 | 1. 打开 `{BASE}/result?q=项目管理` |
| 预期 | - 渲染通用错误页<br>- 提示"服务暂不可用，请稍后重试" |
| 选择器 | `g-error-page` |
| 清理 | 恢复后端服务 |

### F-052：429 全局限流

| 项 | 内容 |
| ---- | ---- |
| 前置 | 短时间内连续 60 次搜索请求 |
| 步骤 | 1. 观察最后一次响应 |
| 预期 | - HTTP 429<br>- 前端渲染通用错误页，含"请求过于频繁" |
| 选择器 | `g-error-page` |
| 清理 | 等待 1 分钟 |

### F-053：断网后搜索 Toast（区别于 F-051 5xx）

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-001 页面（首页空态） |
| 步骤 | 1. `page.context().setOffline(true)` 模拟浏览器断网<br>2. 在 `[data-testid="p-home-search-input"]` 输入 `项目管理`<br>3. 点击 `[data-testid="p-home-search-btn"]` |
| 预期 | - 不渲染通用错误页（[F-051](#f-0515xx-错误页) 区分）<br>- 显示 Toast `[data-testid="g-toast--error"]`，文案含"网络异常，请检查网络后重试"（[08 §2 F-009](../spec/08-验收标准.md)）<br>- Toast 3-5 秒后自动消失<br>- 页面不白屏，搜索框保留输入值 |
| 选择器 | `g-toast--error`, `p-home-search-input` |
| 清理 | `page.context().setOffline(false)` 恢复网络 |

### F-021：浏览器历史栈：后退/前进状态恢复

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + 浏览器历史栈干净 |
| 步骤 | 1. 打开 `{BASE}/`（P-HOME）<br>2. 搜 `项目管理` 跳转 `/result?q=项目管理`（P-RESULT）<br>3. 点击 `CW_OPEN_BASIC` 卡片跳转 `/detail/CW_OPEN_BASIC`（P-DETAIL）<br>4. `page.goBack()` 两次：`/` → `/result?q=项目管理`<br>5. `page.goForward()` 一次回到 `/detail/CW_OPEN_BASIC` |
| 预期 | - 步骤 4：两次返回都正确恢复目标页面<br>  - 第一次回 `/result?q=项目管理`，结果列表存在，`q` 参数与上次一致<br>  - 第二次回 `/`（P-HOME），搜索框为空<br>- 步骤 5：回到 P-DETAIL，详情数据完整<br>- 任何环节不调用额外的 `/access-check` 或 `/search`（[03 §5 状态机](../spec/03-前台门户规格.md)）<br>- 浏览器栈深度 = 3，不存在重复 push |
| 选择器 | `p-home-search-input`, `p-result-search-input`, `p-detail-title` |
| 清理 | 无 |

---

## 7. 跨页面状态

### F-060：从结果页点卡片进详情（开放课件）

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. 点击 `CW_OPEN_BASIC` 对应的 `[data-testid="p-result-card"]` |
| 预期 | - 跳转到 `{BASE}/detail/CW_OPEN_BASIC`<br>- P-DETAIL 渲染 |
| 选择器 | `p-result-card[data-courseware-id="CW_OPEN_BASIC"]`, `p-detail-title` |
| 清理 | 返回结果页 |

### F-061：从结果页点受限卡片进入锁定页

| 项 | 内容 |
| ---- | ---- |
| 前置 | localStorage 干净；F-011 验证受限课件在结果中带锁 |
| 步骤 | 1. 打开 `{BASE}/result?q=Java`<br>2. 点击 `CW_RESTRICTED` 对应的 `[data-testid="p-result-card"]` |
| 预期 | - 跳转到 P-LOCKED<br>- `[data-testid="p-locked-title"]` 文本为 `Java 后端工程实践` |
| 选择器 | `p-result-card[data-courseware-id="CW_RESTRICTED"]`, `p-locked-title` |
| 清理 | 清空 `coursewareTokens` |

> 依据：[08 FTK-002](../spec/08-验收标准.md) / [03 §3.5](../spec/03-前台门户规格.md)。**FTK-001 / FTK-002 已从 v1.1 预留转正为 v1.0 P0 用例**。

### F-062：localStorage 持久化跨刷新

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-032 通过解锁 |
| 步骤 | 1. `await page.reload()` |
| 预期 | - 仍渲染 P-DETAIL（`coursewareTokens` 仍命中） |
| 选择器 | `p-detail-title` |
| 清理 | 清空 `coursewareTokens` |

---

## 8. 浏览器控制台与网络

### F-070：未触发 4xx / 5xx

| 项 | 内容 |
| ---- | ---- |
| 前置 | F-010 页面 |
| 步骤 | 1. `page.on('response', r => { if (r.status() >= 400) errors.push(r.url()) })`<br>2. 静置 5 秒 |
| 预期 | - errors 为空数组 |
| 选择器 | （无） |
| 清理 | 无 |

### F-071：无控制台 error

| 项 | 内容 |
| ---- | ---- |
| 前置 | 任意前台页面 |
| 步骤 | 1. `page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })`<br>2. 静置 5 秒 |
| 预期 | - errors 为空数组 |
| 选择器 | （无） |
| 清理 | 无 |

---

## 9. 用例与数据关系矩阵

| 用例 | 关键数据依赖 |
| ---- | ------------ |
| F-001 ~ F-005 | 无 |
| F-010 | `CW_OPEN_BASIC`, `TAG_PM`, `CAT_PM_GENERAL_INTRO`, `MAT_VIDEO_1` |
| F-011 | `CW_RESTRICTED`, `TAG_BE`, `CAT_SE_BE_JAVA`, `MAT_PPT_1` |
| F-012 | `CW_OPEN_BASIC` + `CW_OPEN_MULTI` |
| F-019a | `CW_OPEN_BASIC`（需有历史栈） |
| F-021 | 全链路（需 `CW_OPEN_BASIC`） |
| F-030 ~ F-038 | `CW_RESTRICTED`, `TKN_A`, `TKN_B` |
| F-040 ~ F-047 | `CW_RESTRICTED`, `CW_OPEN_BASIC`, `CW_OPEN_MULTI` |
| F-048 | `CW_OPEN_BASIC` + `MAT_VIDEO_1` |
| F-049 | `CW_OPEN_MULTI` + `MAT_PDF_1` |
| F-050 / F-053 | `CW_RESTRICTED` + `MAT_PPTX_20`（需 LibreOffice） |
| F-054 | `CW_OPEN_MULTI` + `MAT_PDF_1` |
| F-051 / F-052 / F-055 | 任一样式均可 |
| F-056 | `MAT_PPTX_PENDING`（手动控制 `preview_pdf_path = NULL`） |
| F-050 ~ F-053 | 无 |

---

## 10. 用例覆盖矩阵（前台）

| 文档章节 | 用例 ID |
| -------- | ------- |
| [03 §1 首页空态](../spec/03-前台门户规格.md) | F-001 ~ F-005, F-002a |
| [03 §2 搜索结果页](../spec/03-前台门户规格.md) | F-010 ~ F-020, F-019a |
| [03 §3 受限课件锁定页](../spec/03-前台门户规格.md) | F-030 ~ F-038 |
| [03 §5 详情页](../spec/03-前台门户规格.md) | F-040 ~ F-047 |
| [03 §5a P-VIEWER 素材在线浏览](../spec/03-前台门户规格.md) | F-048 ~ F-056 |
| [03 §11 通用错误页](../spec/03-前台门户规格.md) | F-050 ~ F-053 |
| [09 §5 状态机](../spec/09-UI规格.md) | F-021, F-060 ~ F-062 |
| [08 F01 / F02](../spec/08-验收标准.md) | F-001 ~ F-005, F-002a, F-010 ~ F-020, F-019a, F-040 ~ F-047 |
| [08 F06 / F07](../spec/08-验收标准.md) | F-030 ~ F-038 |
| [08 FTK-001~007](../spec/08-验收标准.md) | F-011, F-030 ~ F-038, F-061 |
| [08 AC-019~025](../spec/08-验收标准.md) | F-049, F-050, F-048, F-051, F-052, F-056 |
| [08 INT-V-001/002](../spec/08-验收标准.md) | INT-V-001 / INT-V-002（在 [test-cases-integration.md §X](./test-cases-integration.md) 详述） |

