# 后台测试用例（A-*）— 鉴权 + 课件管理

> 适用范围：[04-管理后台规格](../spec/04-管理后台规格.md) / [10-API §2~3](../spec/10-API设计规范.md) / [08-验收标准 A01~A03](../spec/08-验收标准.md)。
> 入口：`{BASE}/admin`。
> 数据前置：完成 [setup-teardown.md §3](./setup-teardown.md) 全部 Setup 步骤。

---

## 1. 鉴权（A-LOGIN / A-NAV）

### A-001：未登录访问后台被拦截

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已清空 Cookie |
| 步骤 | 1. 打开 `{BASE}/admin/coursewares` |
| 预期 | - 重定向到 `/admin/login`<br>- 拦截来自前后端：前端路由守卫 + 后端 401 `unauthenticated`（接口调用） |
| 选择器 | `a-login-title` |
| 清理 | 无 |

### A-002：错误 Token 登录失败

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-001 重定向后 |
| 步骤 | 1. `[data-testid="a-login-token-input"]` 输入 `wrong-token`<br>2. 点击 `[data-testid="a-login-submit-btn"]` |
| 预期 | - HTTP 401 `invalid_admin_token`<br>- `[data-testid="a-login-error"]` 文案含"Token 错误"或"鉴权失败"<br>- 仍在 `/admin/login` |
| 选择器 | `a-login-token-input`, `a-login-submit-btn`, `a-login-error` |
| 清理 | 无 |

### A-003：正确 Token 登录成功

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-001 重定向后 |
| 步骤 | 1. 输入 `demo`<br>2. 点击登录 |
| 预期 | - HTTP 200 `ok`<br>- 跳转 `/admin`（课件管理列表）<br>- `[data-testid="a-nav-coursewares"]` 可见 |
| 选择器 | `a-nav-coursewares` |
| 清理 | 无 |

### A-004a：空 Token 登录被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-001 重定向后 |
| 步骤 | 1. 不输入任何字符<br>2. 观察 `[data-testid="a-login-submit-btn"]` 状态 |
| 预期 | - 提交按钮 `disabled`，鼠标 hover 提示 `请输入 Token`（[08 §3 A-004](../spec/08-验收标准.md)）<br>- 若绕过前端（devtools 移除 disabled）提交，后端 400 `missing_token`（[10 §2.1](../spec/10-API设计规范.md)）<br>- 仍在 `/admin/login` |
| 选择器 | `a-login-submit-btn`, `a-login-token-input` |
| 清理 | 无 |

### A-004：退出登录

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003 |
| 步骤 | 1. 点击 `[data-testid="a-nav-logout"]` |
| 预期 | - 清除 Cookie<br>- 跳转 `/admin/login`<br>- 再次访问 `/admin/coursewares` 被拦截 |
| 选择器 | `a-nav-logout`, `a-login-title` |
| 清理 | 无 |

### A-005：会话过期自动跳登录

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003 后手动清 Cookie（模拟过期） |
| 步骤 | 1. 任意操作（点击课件管理 / 翻页） |
| 预期 | - 跳 `/admin/login`<br>- 提示"会话已过期，请重新登录" |
| 选择器 | `a-login-error` |
| 清理 | 无 |

### A-006：导航模块可见性

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003 |
| 步骤 | 1. 观察 `[data-testid="a-nav-*"]` 全部项 |
| 预期 | - 6 项全部可见：`coursewares`, `categories`, `tags`, `materials`, `tokens`, `logout` |
| 选择器 | `a-nav-coursewares`, `a-nav-categories`, `a-nav-tags`, `a-nav-materials`, `a-nav-tokens`, `a-nav-logout` |
| 清理 | 无 |

---

## 2. 课件管理列表（A-CW-LIST）

### A-100：列表渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + A-003 |
| 步骤 | 1. 默认进入 `/admin/coursewares` |
| 预期 | - 4 行：`CW_OPEN_BASIC`, `CW_OPEN_MULTI`, `CW_RESTRICTED`, `CW_LAST_TOKEN`<br>- 访问控制列：前 2 行为 `开放`，后 2 行为 `受限`<br>- 素材数与 `materialIds` 数量一致 |
| 选择器 | `a-cw-row` |
| 清理 | 无 |

### A-101：列表分页

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 后再创建 11 个空标题课件触发分页 |
| 步骤 | 1. 观察 `a-cw-pagination` 切换 |
| 预期 | - 默认 size=10；page=2 渲染剩余 |
| 选择器 | `a-cw-pagination`, `a-cw-row` |
| 清理 | 删除临时课件 |

### A-102：按标题搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-100 |
| 步骤 | 1. `[data-testid="a-cw-search-input"]` 输入 `Java`<br>2. 回车 |
| 预期 | - 仅 `CW_RESTRICTED`, `CW_LAST_TOKEN` 命中（标题均含"Java"或描述相关）<br>- `CW_OPEN_BASIC` 不在结果中 |
| 选择器 | `a-cw-row` |
| 清理 | 清空搜索框 |

### A-103：按访问模式筛选（v1.1+）

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-100 |
| 步骤 | 1. 选择 `accessMode = RESTRICTED` 筛选 |
| 预期 | - 仅 `CW_RESTRICTED`, `CW_LAST_TOKEN`<br>- 实际 v1.0 暂未提供筛选控件时跳过 |
| 选择器 | `a-cw-access-filter`（v1.1+） |
| 清理 | 重置筛选 |

### A-104：列表空态

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成后立即调 [setup-teardown §4.1](./setup-teardown.md) 全部 TD 步骤 |
| 步骤 | 1. 刷新 `/admin/coursewares` |
| 预期 | - `[data-testid="a-cw-empty"]` 可见<br>- 0 行 |
| 选择器 | `a-cw-empty` |
| 清理 | 重新执行 Setup |

---

## 3. 课件新建 / 编辑（A-CW-FORM）

### A-110：进入新建表单

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-100 |
| 步骤 | 1. 点击 `[data-testid="a-cw-new-btn"]` |
| 预期 | - 跳转 `/admin/coursewares/new`<br>- 表单元素全部可见且为空 |
| 选择器 | `a-cw-title-input`, `a-cw-author-input`, `a-cw-category-select`, `a-cw-desc-input`, `a-cw-tags-multi`, `a-cw-access-mode-open`, `a-cw-access-mode-restricted` |
| 清理 | 取消 |

### A-111：标题为空被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 不填标题<br>2. 点击 `[data-testid="a-cw-publish-btn"]` |
| 预期 | - HTTP 400 `courseware_title_required`<br>- 字段下显示错误提示 `[data-testid="g-field-error"]`<br>- 不跳转 |
| 选择器 | `a-cw-publish-btn`, `g-field-error` |
| 清理 | 无 |

### A-112：标题超过 100 字符被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 输入 101 个字符 |
| 预期 | - 前端拦截：maxlength 限制为 100<br>- 或后端 `courseware_title_too_long` 错误码 |
| 选择器 | `a-cw-title-input` |
| 清理 | 清空 |

### A-113：未选分类被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 标题填 `测试`<br>2. 不选分类<br>3. 点击发布 |
| 预期 | - HTTP 400 `courseware_category_required` |
| 选择器 | `a-cw-publish-btn`, `g-field-error` |
| 清理 | 无 |

### A-114：选了非 3 级分类被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 选了 `项目管理`（根分类）<br>2. 发布 |
| 预期 | - HTTP 400 `courseware_category_not_leaf` |
| 选择器 | `a-cw-publish-btn` |
| 清理 | 无 |

### A-115：受限课件未选 Token 被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 选 `软件工程 / 后端 / Java` 分类<br>2. 选 `RESTRICTED`<br>3. 不勾选 Token<br>4. 发布 |
| 预期 | - HTTP 400 `courseware_token_required` |
| 选择器 | `a-cw-access-mode-restricted`, `a-cw-token-multi`, `a-cw-publish-btn` |
| 清理 | 无 |

### A-116：开放课件不能选 Token

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 选 `开放` 模式<br>2. 强行选择 Token（若前端允许） |
| 预期 | - 前端隐藏 `a-cw-token-multi`<br>- 后端 400 `courseware_token_should_be_empty`（若有） |
| 选择器 | `a-cw-token-multi` |
| 清理 | 无 |

### A-117：素材库搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. `[data-testid="a-cw-mat-search-input"]` 输入 `pm`<br>2. 点击 `[data-testid="a-cw-mat-search-btn"]` |
| 预期 | - 命中 `MAT_VIDEO_1`（pm-intro-101.mp4）<br>- `MAT_PPT_1`, `MAT_PPT_2` 不在结果 |
| 选择器 | `a-cw-mat-search-input`, `a-cw-mat-search-btn` |
| 清理 | 清空素材搜索 |

### A-118：素材库按类型筛选

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. `[data-testid="a-cw-mat-type-filter"]` 选 `PPT`<br>2. 点击搜索 |
| 预期 | - 命中 `MAT_PPT_1`, `MAT_PPT_2` |
| 选择器 | `a-cw-mat-type-filter` |
| 清理 | 重置筛选 |

### A-119：关联素材

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-117 命中 `MAT_VIDEO_1` |
| 步骤 | 1. 点击 `[data-testid="a-cw-mat-link-btn"]`（对应 `MAT_VIDEO_1`） |
| 预期 | - 右侧"已关联"区域出现 `[data-testid="a-cw-mat-linked-item"]`<br>- 课件提交时 `materialIds` 包含 `MAT_VIDEO_1` |
| 选择器 | `a-cw-mat-link-btn`, `a-cw-mat-linked-item` |
| 清理 | 无 |

### A-120：移除已关联素材

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-119 |
| 步骤 | 1. 点击 `[data-testid="a-cw-mat-unlink-btn"]`（对应 `MAT_VIDEO_1`） |
| 预期 | - 该项从已关联区域消失 |
| 选择器 | `a-cw-mat-unlink-btn`, `a-cw-mat-linked-item` |
| 清理 | 无 |

### A-121：成功创建开放课件

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 标题 `A-121 测试课件`<br>2. 作者 `Tester`<br>3. 描述 `A-121 用例`<br>4. 分类 `项目管理 / 通用 / 入门`<br>5. 标签 `项目管理, 入门`<br>6. 素材关联 `MAT_VIDEO_1`<br>7. 模式 `OPEN`<br>8. 点击发布 |
| 预期 | - HTTP 200 `ok`<br>- 跳转回列表，新课件在第一行<br>- 列表访问控制列显示 `开放` |
| 选择器 | `a-cw-row`, `a-cw-access-cell` |
| 清理 | 删除该课件（见 A-131） |

### A-122：成功创建受限课件（双 Token）

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 标题 `A-122 受限课件`<br>2. 分类 `软件工程 / 后端 / Java`<br>3. 模式 `RESTRICTED`<br>4. Token 选 `TKN_A, TKN_B`<br>5. 发布 |
| 预期 | - HTTP 200 `ok`<br>- 列表行访问控制列显示 `受限`<br>- 后端表 `courseware_token` 出现 2 条绑定 |
| 选择器 | `a-cw-row`, `a-cw-access-cell` |
| 清理 | 删除该课件 |

### A-123：编辑已有课件切换访问模式

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 已创建 `CW_OPEN_BASIC`（开放） |
| 步骤 | 1. 在列表点击 `CW_OPEN_BASIC` 的编辑按钮 `[data-testid="a-cw-edit-btn"]`<br>2. 切换模式至 `RESTRICTED`<br>3. 选 `TKN_A`<br>4. 发布 |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `access_mode = RESTRICTED`<br>- `courseware_token` 出现 `CW_OPEN_BASIC -> TKN_A` 绑定 |
| 选择器 | `a-cw-edit-btn`, `a-cw-access-mode-restricted`, `a-cw-token-multi` |
| 清理 | 恢复为 `OPEN` 模式 + 解绑 |

### A-124：编辑受限课件时降级为开放

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-123 后 `CW_OPEN_BASIC` 已为 `RESTRICTED` |
| 步骤 | 1. 编辑该课件<br>2. 切换为 `OPEN`<br>3. 发布 |
| 预期 | - HTTP 200 `ok`<br>- `access_mode = OPEN`<br>- 关联 Token 记录被级联清空（[05 §R-12](../spec/05-数据模型.md) 兼容） |
| 选择器 | `a-cw-access-mode-open` |
| 清理 | 无 |

### A-125：表单取消

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 输入部分字段<br>2. 点击 `[data-testid="a-cw-cancel-btn"]`<br>3. 二次确认弹窗点击 `[data-testid="g-confirm-ok"]` |
| 预期 | - 弹窗提示"放弃编辑？"<br>- 确认后返回列表，**不**创建课件 |
| 选择器 | `a-cw-cancel-btn`, `g-confirm-ok` |
| 清理 | 无 |

### A-126：表单取消未输入

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 直接点击取消按钮 |
| 预期 | - 不弹二次确认<br>- 直接返回列表 |
| 选择器 | `a-cw-cancel-btn` |
| 清理 | 无 |

### A-127：编辑受 R-12 保护的受限课件

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_LAST_TOKEN` 仅关联 `TKN_C` |
| 步骤 | 1. 编辑 `CW_LAST_TOKEN`<br>2. 试图移除 `TKN_C`<br>3. 保存 |
| 预期 | - HTTP 422 `last_token_required`<br>- 错误文案"该课件仅剩 1 个有效 Token，请先将课件转为开放模式" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### A-128：新建表单无数据交互不可发布

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. 不填任何字段<br>2. 焦点离开后立即点发布 |
| 预期 | - 多重字段错误展示<br>- 第一个错误字段获焦 |
| 选择器 | `g-field-error` |
| 清理 | 无 |

### A-129：表单断网保存

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-121 前 |
| 步骤 | 1. 停掉后端服务<br>2. 填写字段并提交 |
| 预期 | - 显示 `g-toast--error` 含"网络错误"<br>- 数据保留在表单中不丢失 |
| 选择器 | `g-toast--error` |
| 清理 | 恢复服务 |

### A-130：表单恢复网络后保存

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-129 断网状态下表单已有数据 |
| 步骤 | 1. 恢复服务<br>2. 点击发布 |
| 预期 | - HTTP 200 `ok`（复用已有数据） |
| 选择器 | `g-toast--success` |
| 清理 | 删除该课件 |

### A-131：删除课件（二次确认）

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-121 / A-130 创建的临时课件存在 |
| 步骤 | 1. 列表中找到该行<br>2. 点击 `[data-testid="a-cw-delete-btn"]`<br>3. 二次确认点击 `[data-testid="g-confirm-ok"]` |
| 预期 | - HTTP 200 `ok`<br>- 列表少 1 行<br>- 数据库 `courseware_token` 中相关绑定级联删除 |
| 选择器 | `a-cw-delete-btn`, `g-confirm-ok` |
| 清理 | 无 |

### A-132：删除课件（取消二次确认）

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-131 同 |
| 步骤 | 1. 点击删除<br>2. 二次确认点击 `[data-testid="g-confirm-cancel"]` |
| 预期 | - 课件未被删除<br>- 列表行数不变 |
| 选择器 | `g-confirm-cancel`, `a-cw-row` |
| 清理 | 无 |

### A-133：删除受限课件自动解绑 Token

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_RESTRICTED` 关联 `TKN_A, TKN_B` |
| 步骤 | 1. 删除 `CW_RESTRICTED`<br>2. 查看 Token 管理列表 |
| 预期 | - `TKN_A`, `TKN_B` 仍存在<br>- 关联课件数 = 0（[04 §6.3](../spec/04-管理后台规格.md)） |
| 选择器 | `a-tk-row`, `a-tk-count-cell` |
| 清理 | 重新创建 `CW_RESTRICTED` 绑定 `TKN_A, TKN_B`（或在 Teardown 阶段重做 Setup） |

### A-134：删除课件后素材不联动删除

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_OPEN_BASIC` 关联 `MAT_VIDEO_1` |
| 步骤 | 1. 删除 `CW_OPEN_BASIC`<br>2. 访问素材管理 |
| 预期 | - `MAT_VIDEO_1` 仍在素材列表（[05 §R-08](../spec/05-数据模型.md)） |
| 选择器 | `a-mt-row` |
| 清理 | 无 |

---

## 4. 课件 R-12 业务规则（A-CW-R12）

### A-140：受限课件最后 Token 不可通过编辑移除

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CW_LAST_TOKEN` 仅关联 `TKN_C` |
| 步骤 | 1. 编辑 `CW_LAST_TOKEN`<br>2. 取消勾选 `TKN_C`<br>3. 保存 |
| 预期 | - HTTP 422 `last_token_required` |
| 选择器 | `g-toast--error` |
| 清理 | 重新勾选 |

### A-141：受限课件降级开放可绕过 R-12

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-140 同 |
| 步骤 | 1. 编辑 `CW_LAST_TOKEN`<br>2. 切换为 `OPEN`<br>3. 保存<br>4. **断言**：调 `GET /api/admin/coursewares/CW_LAST_TOKEN`，检查 `accessTokenIds` 为空数组 `[]` 且 `accessTokenCount = 0`<br>5. **断言**：进入 Token 管理列表，`TKN_C` 行的 `关联课件数` 列为 `0`（[05 §R-12](../spec/05-数据模型.md)） |
| 预期 | - HTTP 200 `ok`<br>- `access_mode = OPEN`<br>- `courseware_token` 中 `CW_LAST_TOKEN` 绑定**自动**被清空（同事务）<br>- Token 本身 `TKN_C` 不被删除（仅解除关联） |
| 选择器 | `a-cw-access-mode-open`, `a-tk-row`, `a-tk-count-cell` |
| 清理 | 恢复 `RESTRICTED` + 重新绑定 `TKN_C` |

---

## 5. 状态机：表单编辑态切换（A-CW-STATE）

### A-150：表单 → 列表 → 表单 切换

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-110 |
| 步骤 | 1. A-110 进入新建表单<br>2. 点击顶部 Logo `[data-testid="a-nav-coursewares"]`<br>3. 再次点击新建 |
| 预期 | - 路由切换正确<br>- 二次新建表单初始为空 |
| 选择器 | `a-cw-title-input` |
| 清理 | 无 |

### A-151：编辑表单字段变更

| 项 | 内容 |
| ---- | ---- |
| 前置 | 编辑 `CW_OPEN_BASIC` 表单 |
| 步骤 | 1. 修改标题为 `项目管理入门（已更新）`<br>2. 保存 |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `title` 字段更新 |
| 选择器 | `a-cw-title-input`, `a-cw-row` |
| 清理 | 恢复原标题 |

### A-152：编辑表单撤销修改

| 项 | 内容 |
| ---- | ---- |
| 前置 | 编辑 `CW_OPEN_BASIC` 表单 |
| 步骤 | 1. 修改标题<br>2. 点击取消 → 二次确认 → 取消 |
| 预期 | - 数据库无变化 |
| 选择器 | `a-cw-row` |
| 清理 | 无 |

---

## 6. 课件素材库搜索边界

### A-160：素材库搜索关键词为空

| 项 | 内容 |
| ---- | ---- |
| 前置 | 编辑表单 |
| 步骤 | 1. 不输入关键词<br>2. 点击搜索按钮 |
| 预期 | - 返回全量素材（或前端禁用按钮） |
| 选择器 | `a-cw-mat-search-btn` |
| 清理 | 无 |

### A-161：素材库搜索无结果

| 项 | 内容 |
| ---- | ---- |
| 前置 | 编辑表单 |
| 步骤 | 1. 输入 `XXXNOTFOUND` |
| 预期 | - 列表为空，提示"暂无素材" |
| 选择器 | `a-cw-mat-empty`（前端约定） |
| 清理 | 无 |

### A-162：素材库分页

| 项 | 内容 |
| ---- | ---- |
| 前置 | 编辑表单 |
| 步骤 | 1. 翻页至 page=2 |
| 预期 | - 加载下一页素材<br>- 已关联项持续显示 |
| 选择器 | `a-cw-mat-pagination`（前端约定） |
| 清理 | 无 |

---

## 7. 课件搜索筛选

### A-170：列表搜索大小写

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-100 |
| 步骤 | 1. 输入 `java`（小写） |
| 预期 | - 命中含 `Java` 的课件（`CW_RESTRICTED` / `CW_LAST_TOKEN`） |
| 选择器 | `a-cw-row` |
| 清理 | 清空 |

### A-171：列表搜索关键词过长

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-100 |
| 步骤 | 1. 输入 201 字符 |
| 预期 | - 前端截断 / 后端 400 |
| 选择器 | `a-cw-search-input` |
| 清理 | 清空 |

---

## 8. 素材上传与预览生成（A-MAT-PREVIEW，v1.2+）

> 适用范围：[04 §3.x 素材管理上传流程](../spec/04-管理后台规格.md) / [10 §5.2.4 公开素材流式接口](../spec/10-API设计规范.md) / [03 §5a P-VIEWER](../spec/03-前台门户规格.md)。
> 依赖：完成 [setup-teardown.md §3](./setup-teardown.md) 全部 Setup 步骤；宿主环境已安装 LibreOffice（参见 [deploy/README.md §7.8](../../deploy/README.md)），否则 AD-181 跳过。

### AD-180：上传 PPTX 后立即刷新详情，可在 P-VIEWER-PPT 看到幻灯片预览

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003 + 已创建 `CW_OPEN_BASIC`；本地有 fixture `courseware-with-pptx-20slides.pptx`（参见 [test-data.md §2.x](./test-data.md)） |
| 步骤 | 1. 进入素材管理 `/admin/materials`<br>2. 上传 `courseware-with-pptx-20slides.pptx`，类型 `PPT`<br>3. 等待后端返回 200 后将该素材关联到 `CW_OPEN_BASIC`<br>4. 切到前台 `/{BASE}/detail/CW_OPEN_BASIC`<br>5. 点击该素材的 `[data-testid="p-detail-material-online-btn"]`（文案"在线浏览"） |
| 预期 | - 上传成功响应 `ok`，DB 中 `material.preview_pdf_path IS NOT NULL` 且指向 `storage_path` 同级 `*.pdf`<br>- 前台 P-VIEWER-PPT 渲染：`p-viewer-ppt-indicator` 显示 `1 / 20`，画布可见<br>- 切换下一张后指示器变为 `2 / 20`<br>- 返回 P-DETAIL 时 URL 含 `view=detail` |
| 选择器 | `p-detail-material-online-btn`, `p-viewer-ppt`, `p-viewer-ppt-indicator`, `p-viewer-ppt-next`, `p-viewer-back-btn` |
| 清理 | 解除素材关联、删除素材（同步清理 `preview_pdf_path` 文件） |

### AD-181：上传损坏 PPTX 不被阻断，详情页降级为下载提示

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-003；本地有 fixture `corrupt.pptx`（非合法 Office Open XML，例如仅 1KB 随机字节；参见 [test-data.md §2.x](./test-data.md)） |
| 步骤 | 1. 进入素材管理 `/admin/materials`<br>2. 上传 `corrupt.pptx`，类型 `PPT`<br>3. 后端返回 200 后将该素材关联到 `CW_OPEN_BASIC`<br>4. 切到前台 `/{BASE}/detail/CW_OPEN_BASIC`<br>5. 观察素材项右侧按钮 |
| 预期 | - 上传 HTTP 200 `ok`（[04 §3.x](../spec/04-管理后台规格.md)：转换失败不阻断上传）<br>- DB 中 `material.preview_pdf_path IS NULL`<br>- 前台素材项右侧 `[data-testid="p-detail-material-online-btn"]` 文案降级为"下载到本地"或 disabled + tooltip `预览生成中`<br>- 公开 `/stream` 接口对该素材返回 `Content-Disposition: attachment` 而非 inline<br>- 后端日志（`ppt_to_pdf.convert`）含 `convert failed` 字样（warn 级别） |
| 选择器 | `p-detail-material-online-btn`, `p-detail-material-download-link`（降级链接），`p-viewer-download-link`（若有） |
| 清理 | 删除损坏素材记录 |

### AD-182：旧数据无 preview_pdf_path 时自动降级

| 项 | 内容 |
| ---- | ---- |
| 前置 | 通过 SQL 注入或 fixture 构造一条 `preview_pdf_path IS NULL` 的 PPT 素材；该素材未被关联到任何课件 |
| 步骤 | 1. 后台手动将该素材关联到 `CW_OPEN_BASIC`<br>2. 前台进入 `/{BASE}/detail/CW_OPEN_BASIC`<br>3. 点击该素材按钮 |
| 预期 | - 接口返回 200 但 `Content-Disposition: attachment`<br>- 前台按钮降级为"下载到本地"，不进入 P-VIEWER-PPT |
| 选择器 | `p-detail-material-online-btn`, `p-detail-material-download-link` |
| 清理 | 解除关联并删除素材 |

### AD-183：删除素材同步清理 preview_pdf_path

| 项 | 内容 |
| ---- | ---- |
| 前置 | AD-180 已成功创建带 `preview_pdf_path` 的 PPT 素材 |
| 步骤 | 1. 素材管理 `/admin/materials` 找到该素材<br>2. 点击 `[data-testid="a-mt-delete-btn"]`<br>3. 二次确认 |
| 预期 | - HTTP 200 `ok`<br>- 素材表行被删除<br>- `preview_pdf_path` 指向的磁盘 PDF 文件被同步删除（[05 §2.4 业务规则](../spec/05-数据模型.md)） |
| 选择器 | `a-mt-delete-btn`, `g-confirm-ok` |
| 清理 | 无 |

---

## 9. 用例与数据关系矩阵

| 用例 | 关键数据 |
| ---- | -------- |
| A-001 ~ A-006, A-004a | 无 |
| A-100 ~ A-104 | 全部 4 个课件 |
| A-110 ~ A-134 | 全部 4 个课件 + `TKN_A/B/C` |
| A-140 ~ A-141 | `CW_LAST_TOKEN`, `TKN_C` |
| A-150 ~ A-171 | `CW_OPEN_BASIC`, 全部素材 |
| AD-180 ~ AD-183 | `courseware-with-pptx-20slides.pptx`、`corrupt.pptx`、旧数据素材（`preview_pdf_path IS NULL`） |

---

## 10. 用例覆盖矩阵

| 文档章节 | 用例 ID |
| -------- | ------- |
| [04 §2 鉴权](../spec/04-管理后台规格.md) | A-001 ~ A-006, A-004a |
| [04 §3 课件管理](../spec/04-管理后台规格.md) | A-100 ~ A-171 |
| [04 §3.x 素材管理上传流程（v1.2+）](../spec/04-管理后台规格.md) | AD-180, AD-181, AD-183 |
| [05 §2.4 Material 业务规则（v1.2+）](../spec/05-数据模型.md) | AD-180, AD-183 |
| [08 A01](../spec/08-验收标准.md) | A-001 ~ A-006, A-004a |
| [08 A02 课件](../spec/08-验收标准.md) | A-110 ~ A-134, A-140 ~ A-152 |
| [08 A02 课件、AC-019/020/021（v1.2+）](../spec/08-验收标准.md) | AD-180, AD-181 |
| [10 §3.2.3 课件错误码](../spec/10-API设计规范.md) | A-111 ~ A-117, A-127, A-140 |
| [10 §3.2.5 鉴权错误码](../spec/10-API设计规范.md) | A-002, A-004a |
| [10 §5.2.4 公开素材流式接口（v1.2+）](../spec/10-API设计规范.md) | AD-180, AD-181, AD-182 |
