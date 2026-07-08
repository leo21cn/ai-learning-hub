# 选择器与元素命名规范（Browser Agent 友好）

> 本文件为 Browser Agent / Playwright / Cypress 自动化测试约定的**前端实现契约**。
> 所有 `data-testid` / `aria-label` 在前后端实现时**必须保留**，否则测试用例的 `selector` 列会失效。

---

## 1. 总约定

| 维度 | 约定 |
| ---- | ---- |
| 测试属性 | `data-testid`（首选）/ `aria-label`（兜底） |
| 选择器策略 | `<testid-prefix>-<entity>-<action?>`，中划线分隔，全小写 |
| 命名空间 | 前台 `p-*`，后台 `a-*`，全局 `g-*` |
| 文本依赖 | 仅在断言文案时使用（用 `expect(...).toHaveText('...')`），**不**作为定位手段 |
| ID 依赖 | **不**依赖后端数据库自增 ID；如需，用 `data-courseware-id` 等业务属性 |
| 稳定排序 | 列表项可重复时附加 `data-test-index`（从 0 递增），便于定位"第 N 项" |

---

## 2. 通用组件

| 组件 | `data-testid` | 说明 |
| ---- | ------------- | ---- |
| 顶部品牌 Logo | `g-logo` | 点击回首页 |
| 主按钮（蓝色） | `g-btn-primary` | 提交、保存、发布等 |
| 次按钮（文字） | `g-btn-text` | 取消、返回等 |
| 危险按钮 | `g-btn-danger` | 删除等（与二次确认联动） |
| Toast 容器 | `g-toast` | 自动消失，断言用 `g-toast--success` / `g-toast--error` |
| 二次确认弹窗 | `g-confirm-dialog` | 子项：`g-confirm-ok` / `g-confirm-cancel` |
| 表单输入框 | `g-input-<field>` | 与字段名同后缀 |
| 错误提示 | `g-field-error` | 与最近输入框同级 |

---

## 3. 前台门户（`p-*`）

### 3.1 首页空态（P-HOME）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 搜索输入框 | `p-home-search-input` | `搜索课件` |
| 搜索按钮 | `p-home-search-btn` | `搜索` |
| 品牌标题 | `p-home-title` | - |

### 3.2 搜索结果页（P-RESULT）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 顶部 Logo | `p-result-logo` | - |
| 顶部搜索输入框 | `p-result-search-input` | - |
| AI 智能搜索标签 | `p-result-ai-badge` | `AI 智能搜索` |
| 命中数量 | `p-result-count` | - |
| 清空全部按钮 | `p-result-clear-btn` | `清空全部` |
| 课件卡片 | `p-result-card` | 属性 `data-courseware-id` / `data-access-mode`（`open` / `restricted`） |
| 受限课件 🔒 图标 | `p-result-card-lock` | `该课件需要访问令牌` |
| 加载态文案 | `p-result-loading` | - |
| 空结果 📭 图标 | `p-result-empty-icon` | - |
| 空结果文案 | `p-result-empty-text` | - |

### 3.3 受限课件锁定页（P-LOCKED）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 课件标题 | `p-locked-title` | - |
| Token 输入框 | `p-locked-token-input` | `访问令牌` |
| 解锁按钮 | `p-locked-unlock-btn` | `解锁` |
| 返回搜索按钮 | `p-locked-back-btn` | `返回搜索` |
| 错误提示 | `p-locked-error` | - |

### 3.4 课件详情页（P-DETAIL）

> **v1.2 起**：P-DETAIL 不再提供"下载到本地"入口，`p-detail-material-download-link`
> 与 `p-detail-pdf-link` 均被移除，仅保留 `p-detail-material-browse-btn`。

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| H1 标题 | `p-detail-title` | - |
| 作者 | `p-detail-author` | - |
| 分类路径 | `p-detail-category-path` | - |
| 标签列表 | `p-detail-tags` | - |
| 描述 | `p-detail-description` | - |
| 素材项 | `p-detail-material` | 属性 `data-material-id` / `data-material-type` |
| 素材项“在线浏览”按钮 | `p-detail-material-browse-btn` | `在线浏览` |
| 返回搜索 | `p-detail-back-btn` | `返回搜索` |
| Logo | `p-detail-logo` | - |
| 视频播放器 | `p-detail-video` | - |

### 3.5 素材在线浏览页（P-VIEWER）

> **v1.2 起**：P-VIEWER 与 P-DETAIL 三种样式均不提供任何“下载到本地”入口，
> 不暴露 `/api/public/materials/{id}/file`。`p-viewer-download-link`、
> `p-detail-material-download-link` 与 `p-detail-pdf-link` 均被移除。
> 错误 / 加载态文案保留但不提供下载链接。

#### 3.5.0 公共顶栏（三种样式共享）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 返回按钮 | `p-viewer-back-btn` | `返回` |
| 文件名 | `p-viewer-title` | - |
| 类型徽标 | `p-viewer-type-badge` | - |
| Logo | `p-viewer-logo` | `返回首页` |

#### 3.5.1 视频样式（P-VIEWER-VIDEO）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 视频播放器根 | `p-viewer-video` | - |
| 信息面板容器 | `p-viewer-video-info` | - |
| 信息面板文件名 | `p-viewer-video-info-name` | - |
| 信息面板时长 | `p-viewer-video-info-duration` | - |
| 信息面板大小 | `p-viewer-video-info-size` | - |
| 加载文案 | `p-viewer-video-loading` | - |
| 错误文案 | `p-viewer-video-error` | - |

#### 3.5.2 PDF 阅读样式（P-VIEWER-PDF）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 根容器 | `p-viewer-pdf` | - |
| 顶部工具条 | `p-viewer-pdf-toolbar` | - |
| 缩放 - 按钮 | `p-viewer-pdf-zoom-out` | `缩小` |
| 缩放 + 按钮 | `p-viewer-pdf-zoom-in` | `放大` |
| 缩放比例文本 | `p-viewer-pdf-zoom-label` | - |
| 页码气泡 | `p-viewer-pdf-page-indicator` | `第 N / M 页`，`aria-live="polite"` |
| 加载文案 | `p-viewer-pdf-loading` | - |
| 渲染错误文案 | `p-viewer-pdf-error` | - |

#### 3.5.3 PPT 幻灯片样式（P-VIEWER-PPT）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 根容器 | `p-viewer-ppt` | - |
| 图片 | `p-viewer-ppt-image` | - |
| 上一张按钮 | `p-viewer-ppt-prev` | `上一张` |
| 下一张按钮 | `p-viewer-ppt-next` | `下一张` |
| 页码指示器 | `p-viewer-ppt-indicator` | `第 N / M 张` |
| 全屏按钮 | `p-viewer-ppt-fullscreen` | `全屏` |
| 控制条容器 | `p-viewer-ppt-controls` | - |
| 加载文案 | `p-viewer-ppt-loading` | - |
| 错误文案 | `p-viewer-ppt-error` | - |
| 预览未生成提示 | `p-viewer-ppt-preview-pending` | - |

---

## 4. 后台鉴权（A-LOGIN）

| 元素 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 标题 | `a-login-title` | - |
| Token 输入框 | `a-login-token-input` | `Admin Token` |
| 登录按钮 | `a-login-submit-btn` | `登录` |
| 错误提示 | `a-login-error` | - |

---

## 5. 后台导航（A-NAV）

| 模块 | `data-testid` | `aria-label` |
| ---- | ------------- | ------------ |
| 课件管理 | `a-nav-coursewares` | `课件管理` |
| 分类管理 | `a-nav-categories` | `分类管理` |
| 标签管理 | `a-nav-tags` | `标签管理` |
| 素材管理 | `a-nav-materials` | `素材管理` |
| Token 管理 | `a-nav-tokens` | `Token 管理` |
| 退出 | `a-nav-logout` | `退出` |

---

## 6. 课件管理

### 6.1 列表页（A-CW-LIST）

| 元素 | `data-testid` |
| ---- | ------------- |
| 搜索框 | `a-cw-search-input` |
| 新建按钮 | `a-cw-new-btn` |
| 表格行 | `a-cw-row`（属性 `data-courseware-id`） |
| 访问控制列 | `a-cw-access-cell` |
| 操作列编辑 | `a-cw-edit-btn` |
| 操作列删除 | `a-cw-delete-btn` |
| 分页 | `a-cw-pagination` |
| 空态 | `a-cw-empty` |

### 6.2 表单页（A-CW-FORM）

| 元素 | `data-testid` |
| ---- | ------------- |
| 标题输入框 | `a-cw-title-input` |
| 作者输入框 | `a-cw-author-input` |
| 分类下拉 | `a-cw-category-select` |
| 描述输入框 | `a-cw-desc-input` |
| 标签多选 | `a-cw-tags-multi` |
| 素材库搜索框 | `a-cw-mat-search-input` |
| 素材库类型筛选 | `a-cw-mat-type-filter` |
| 素材库搜索按钮 | `a-cw-mat-search-btn` |
| 素材库关联按钮 | `a-cw-mat-link-btn` |
| 已关联素材项 | `a-cw-mat-linked-item` |
| 移除素材关联 | `a-cw-mat-unlink-btn` |
| 访问模式 单选 | `a-cw-access-mode-open` / `a-cw-access-mode-restricted` |
| 关联 Token 多选 | `a-cw-token-multi` |
| 发布按钮 | `a-cw-publish-btn` |
| 取消按钮 | `a-cw-cancel-btn` |

---

## 7. 分类管理（A-CT-TREE）

| 元素 | `data-testid` |
| ---- | ------------- |
| 新建根分类按钮 | `a-ct-new-root-btn` |
| 分类行 | `a-ct-row`（属性 `data-category-id` / `data-level`） |
| 子分类按钮 | `a-ct-add-child-btn` |
| 行内编辑按钮 | `a-ct-edit-btn` |
| 行内删除按钮 | `a-ct-delete-btn` |
| 行内输入框（编辑态） | `a-ct-name-input` |

---

## 8. 标签管理（A-TG-LIST）

| 元素 | `data-testid` |
| ---- | ------------- |
| 新建标签按钮 | `a-tg-new-btn` |
| 标签行 | `a-tg-row`（属性 `data-tag-id`） |
| 重命名按钮 | `a-tg-rename-btn` |
| 删除按钮 | `a-tg-delete-btn` |
| 关联课件数列 | `a-tg-count-cell` |
| 新建弹窗名称输入框 | `a-tg-name-input` |
| 创建按钮 | `a-tg-create-btn` |
| 取消按钮 | `a-tg-cancel-btn` |

---

## 9. 素材管理（A-MT-LIST）

| 元素 | `data-testid` |
| ---- | ------------- |
| 上传按钮 | `a-mt-upload-btn` |
| 搜索框 | `a-mt-search-input` |
| 类型筛选 | `a-mt-type-filter` |
| 素材行 | `a-mt-row`（属性 `data-material-id`） |
| 删除按钮 | `a-mt-delete-btn` |
| 上传弹窗文件输入 | `a-mt-file-input` |
| 确认上传 | `a-mt-confirm-upload-btn` |
| 取消 | `a-mt-cancel-upload-btn` |

---

## 10. Token 管理（A-TK-LIST）

| 元素 | `data-testid` |
| ---- | ------------- |
| 搜索框 | `a-tk-search-input` |
| 新建按钮 | `a-tk-new-btn` |
| Token 行 | `a-tk-row`（属性 `data-token-id`） |
| 重新生成按钮 | `a-tk-regen-btn` |
| 删除按钮 | `a-tk-delete-btn` |
| 名称输入框（行内） | `a-tk-label-input` |
| 名称保存按钮 | `a-tk-label-save-btn` |
| 新建弹窗名称输入 | `a-tk-new-label-input` |
| 新建弹窗创建 | `a-tk-new-create-btn` |
| 新建弹窗取消 | `a-tk-new-cancel-btn` |
| 一次性明文展示容器 | `a-tk-once-value` |
| 复制明文按钮 | `a-tk-copy-btn` |
| 关联课件数单元格 | `a-tk-count-cell` |

---

## 11. 选择器解析优先级（Browser Agent 实现）

```text
1. data-testid（最稳定，跨样式 / 文案变动不破）
2. aria-label（兜底，无障碍语义）
3. role + name（无 data-testid 时使用，如 role="button" + name="登录"）
4. 文本匹配（最后兜底，仅用于断言，不用于定位）
```

> 任何修改前端实现时，**禁止删除已有 `data-testid`**；新增控件**必须**按本规范命名。

---

## 12. Browser Agent 调用约定

| 操作 | 推荐 API | 示例 |
| ---- | -------- | ---- |
| 点击 | `page.click('[data-testid="p-home-search-btn"]')` | - |
| 输入 | `page.fill('[data-testid="a-cw-title-input"]', '项目管理入门')` | - |
| 选择 | `page.selectOption('[data-testid="a-cw-category-select"]', { label: '...' })` | - |
| 断言文本 | `await expect(page.locator('[data-testid="p-result-count"]')).toHaveText(/找到 \d+ 个课件/)` | - |
| 等待 | `await page.waitForResponse(r => r.url().includes('/api/public/coursewares/search'))` | 网络稳定后断言 |
| localStorage | `await page.evaluate(() => localStorage.clear())` | Setup 阶段 |