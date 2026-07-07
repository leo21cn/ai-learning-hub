# 后台测试用例 — 分类 / 标签 / 素材 / Token 管理

> 适用范围：[04-管理后台规格 §4~7](../spec/04-管理后台规格.md) / [10-API §3.2](../spec/10-API设计规范.md) / [08 A03~A06](../spec/08-验收标准.md)。
> 入口：`{BASE}/admin/{categories|tags|materials|tokens}`。
> 数据前置：完成 [setup-teardown.md §3](./setup-teardown.md) 全部 Setup 步骤。

---

## 1. 分类管理（A-CT-TREE）

### C-001：分类树正确渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + 登录 |
| 步骤 | 1. 导航至 `/admin/categories` |
| 预期 | - 8 个分类全部出现<br>- 三级层级：根 → 二级 → 三级<br>- 缩进正确 |
| 选择器 | `a-ct-row[data-category-id]` |
| 清理 | 无 |

### C-002：新建根分类

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-001 |
| 步骤 | 1. 点击 `[data-testid="a-ct-new-root-btn"]`<br>2. 行内输入框输入 `业务领域`<br>3. 回车保存 |
| 预期 | - HTTP 200 `ok`<br>- 树顶部多一行 `业务领域` |
| 选择器 | `a-ct-new-root-btn`, `a-ct-name-input` |
| 清理 | 删除该根分类 |

### C-003：根分类下新建子分类

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-001 |
| 步骤 | 1. 在 `项目管理` 行点击 `[data-testid="a-ct-add-child-btn"]`<br>2. 输入 `PM 子项`<br>3. 保存 |
| 预期 | - HTTP 200 `ok`<br>- 树中出现 `项目管理 / PM 子项` 二级节点 |
| 选择器 | `a-ct-add-child-btn`, `a-ct-name-input` |
| 清理 | 删除该子分类 |

### C-004：超过 3 级被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-003 同（3 级 `入门` 已存在） |
| 步骤 | 1. 在 `入门` 行点击添加子分类<br>2. 输入 `第4级`<br>3. 保存 |
| 预期 | - HTTP 409 `category_max_level`<br>- 弹错误提示 |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### C-005：同父节点重名被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-001 |
| 步骤 | 1. 试图新建子分类 `通用`（与已有 `CAT_PM_GENERAL` 同父） |
| 预期 | - HTTP 409 `category_name_conflict` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### C-006：重命名分类

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-001 |
| 步骤 | 1. 在 `项目管理` 行点击 `[data-testid="a-ct-edit-btn"]`<br>2. 改名 `项目管理（重命名）`<br>3. 保存 |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `name` 字段更新 |
| 选择器 | `a-ct-edit-btn`, `a-ct-name-input` |
| 清理 | 恢复原名 |

### C-007：删除叶子分类

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成后 |
| 步骤 | 1. 在 `Scrum` 行点击删除<br>2. 二次确认 `g-confirm-ok` |
| 预期 | - HTTP 200 `ok`<br>- 树中少 1 行 |
| 选择器 | `a-ct-delete-btn`, `g-confirm-ok` |
| 清理 | 重新创建 |

### C-008：删除有课件的分类被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | `CAT_PM_GENERAL_INTRO` 关联 `CW_OPEN_BASIC` |
| 步骤 | 1. 试图删除 `入门` |
| 预期 | - HTTP 409 `category_in_use`<br>- 错误文案"该分类下仍有课件" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### C-009：删除有子分类的父分类被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | `项目管理` 有 `通用, 敏捷` 两个子 |
| 步骤 | 1. 试图删除 `项目管理` |
| 预期 | - HTTP 409 `category_has_children` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### C-010：分类名不能为空

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-002 |
| 步骤 | 1. 输入空字符串 |
| 预期 | - 前端禁用保存按钮<br>- 后端 400 `category_name_required`（若绕过前端） |
| 选择器 | `a-ct-name-input` |
| 清理 | 无 |

### C-011：分类名超过 50 字符

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-002 |
| 步骤 | 1. 输入 51 字符 |
| 预期 | - 前端 maxlength 限制为 50<br>- 后端 400（若绕过） |
| 选择器 | `a-ct-name-input` |
| 清理 | 无 |

### C-012：分类拖拽排序（v1.1+）

| 项 | 内容 |
| ---- | ---- |
| 前置 | 根分类 ≥ 2 |
| 步骤 | 1. 拖拽 `软件工程` 至 `项目管理` 前 |
| 预期 | - HTTP 200 `ok`<br>- `sort_order` 更新 |
| 选择器 | `a-ct-row` |
| 清理 | 恢复原顺序 |

> v1.0 不支持排序时跳过。

---

## 2. 标签管理（A-TG-LIST）

### T-001：标签列表渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + 登录 |
| 步骤 | 1. 导航至 `/admin/tags` |
| 预期 | - 5 行：`TAG_PM, TAG_AGILE, TAG_BE, TAG_INTRO, TAG_TEMP`<br>- `TAG_PM` 关联课件数 = 2<br>- `TAG_TEMP` 关联课件数 = 0 |
| 选择器 | `a-tg-row`, `a-tg-count-cell` |
| 清理 | 无 |

### T-002：新建标签

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-001 |
| 步骤 | 1. 点击 `[data-testid="a-tg-new-btn"]`<br>2. 在弹窗输入 `A-标签测试`<br>3. 点击 `[data-testid="a-tg-create-btn"]` |
| 预期 | - HTTP 200 `ok`<br>- 列表多 1 行 |
| 选择器 | `a-tg-new-btn`, `a-tg-name-input`, `a-tg-create-btn` |
| 清理 | 删除该标签（与 T-004 关联） |

### T-003：重名标签被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-001 |
| 步骤 | 1. 试图新建 `项目管理`（重复） |
| 预期 | - HTTP 409 `tag_name_conflict` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### T-004：重命名标签

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-002 已创建 `A-标签测试` |
| 步骤 | 1. 在该行点击 `[data-testid="a-tg-rename-btn"]`<br>2. 改名 `A-标签测试（已更新）`<br>3. 保存 |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `name` 字段更新 |
| 选择器 | `a-tg-rename-btn`, `a-tg-name-input` |
| 清理 | 无 |

### T-005：重命名为已存在标签

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-002 同 |
| 步骤 | 1. 试图改名为 `敏捷`（已存在） |
| 预期 | - HTTP 409 `tag_name_conflict` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### T-006：删除未被引用的标签

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TAG_TEMP` 关联课件数 = 0 |
| 步骤 | 1. 点击 `[data-testid="a-tg-delete-btn"]`<br>2. 二次确认 |
| 预期 | - HTTP 200 `ok`<br>- 列表少 1 行 |
| 选择器 | `a-tg-delete-btn`, `g-confirm-ok` |
| 清理 | 无 |

### T-007：删除被引用的标签

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TAG_PM` 关联 2 个课件 |
| 步骤 | 1. 试图删除 `TAG_PM` |
| 预期 | - HTTP 409 `tag_in_use`<br>- 错误文案"该标签仍被引用" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### T-008：标签取消新建

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-002 弹窗打开 |
| 步骤 | 1. 输入字符<br>2. 点击 `[data-testid="a-tg-cancel-btn"]` |
| 预期 | - 弹窗关闭<br>- 标签未创建 |
| 选择器 | `a-tg-cancel-btn` |
| 清理 | 无 |

### T-009：标签名为空

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-002 弹窗 |
| 步骤 | 1. 不输入字符<br>2. 点击创建 |
| 预期 | - 创建按钮 disabled<br>- 字段错误提示 |
| 选择器 | `a-tg-create-btn`, `g-field-error` |
| 清理 | 无 |

### T-010：标签名超过 30 字符

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-002 弹窗 |
| 步骤 | 1. 输入 31 字符 |
| 预期 | - 前端 maxlength=30<br>- 后端 400（若绕过） |
| 选择器 | `a-tg-name-input` |
| 清理 | 无 |

### T-011：标签列表搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-001 |
| 步骤 | 1. 输入 `敏捷` |
| 预期 | - 仅 `TAG_AGILE` 命中 |
| 选择器 | `a-tg-row` |
| 清理 | 清空 |

### T-012：标签列表分页

| 项 | 内容 |
| ---- | ---- |
| 前置 | 创建 11+ 临时标签 |
| 步骤 | 1. 翻页 |
| 预期 | - 默认 size=10 |
| 选择器 | `a-tg-pagination` |
| 清理 | 删除临时标签 |

---

## 3. 素材管理（A-MT-LIST）

### M-001：素材列表渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + 登录 |
| 步骤 | 1. 导航至 `/admin/materials` |
| 预期 | - 4 行：`MAT_VIDEO_1, MAT_PDF_1, MAT_PPT_1, MAT_PPT_2` |
| 选择器 | `a-mt-row` |
| 清理 | 无 |

### M-002：上传 PDF 素材

| 项 | 内容 |
| ---- | ---- |
| 前置 | ECS 已预置文件 |
| 步骤 | 1. 点击 `[data-testid="a-mt-upload-btn"]`<br>2. `[data-testid="a-mt-file-input"]` 选 `scrum-guide-2nd.pdf`<br>3. 点击 `[data-testid="a-mt-confirm-upload-btn"]` |
| 预期 | - HTTP 200 `ok`<br>- 列表多 1 行（`MAT_PDF_2`）<br>- `data-testid` 形如 `a-mt-row[data-material-id="MAT_PDF_2"]` |
| 选择器 | `a-mt-upload-btn`, `a-mt-file-input`, `a-mt-confirm-upload-btn` |
| 清理 | 删除该素材 |

### M-003：上传超过 200MB 文件被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | `oversize.mp4` 已预置 |
| 步骤 | 1. 上传 `oversize.mp4` |
| 预期 | - HTTP 413 `material_size_exceeded`<br>- 错误文案"文件大小不能超过 200MB" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### M-004：上传非法扩展名被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | `notallowed.exe` 已预置 |
| 步骤 | 1. 上传 `notallowed.exe` |
| 预期 | - HTTP 400 `material_extension_invalid`<br>- 错误文案"仅支持 PDF/PPT/VIDEO" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### M-005：素材搜索

| 项 | 内容 |
| ---- | ---- |
| 前置 | M-001 |
| 步骤 | 1. `[data-testid="a-mt-search-input"]` 输入 `java`<br>2. 搜索 |
| 预期 | - 命中 `MAT_PPT_1`（java-backend.pptx）<br>- 其他不命中 |
| 选择器 | `a-mt-search-input`, `a-mt-row` |
| 清理 | 清空 |

### M-006：素材按类型筛选

| 项 | 内容 |
| ---- | ---- |
| 前置 | M-001 |
| 步骤 | 1. `[data-testid="a-mt-type-filter"]` 选 `PPT` |
| 预期 | - 命中 `MAT_PPT_1, MAT_PPT_2`<br>- 不含 `MAT_VIDEO_1, MAT_PDF_1` |
| 选择器 | `a-mt-type-filter`, `a-mt-row` |
| 清理 | 重置 |

### M-007：删除未被引用的素材

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PDF_1` 关联 `CW_OPEN_MULTI`；新建 `MAT_PDF_TEST` 不被任何课件引用 |
| 步骤 | 1. 删除 `MAT_PDF_TEST` |
| 预期 | - HTTP 200 `ok`<br>- 数据库 `documents` 少 1 行 |
| 选择器 | `a-mt-delete-btn`, `g-confirm-ok` |
| 清理 | 无 |

### M-008：删除被引用的素材被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PDF_1` 关联 `CW_OPEN_MULTI` |
| 步骤 | 1. 试图删除 `MAT_PDF_1` |
| 预期 | - HTTP 409 `material_in_use`<br>- 错误文案"该素材仍被课件引用" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### M-009：上传中取消

| 项 | 内容 |
| ---- | ---- |
| 前置 | M-002 上传弹窗打开 |
| 步骤 | 1. 选文件后，点击 `[data-testid="a-mt-cancel-upload-btn"]` |
| 预期 | - 弹窗关闭<br>- 列表行数不变 |
| 选择器 | `a-mt-cancel-upload-btn`, `a-mt-row` |
| 清理 | 无 |

### M-010：上传重复文件（同名不同内容）

| 项 | 内容 |
| ---- | ---- |
| 前置 | `pm-intro-101.mp4` 已存在 |
| 步骤 | 1. 重新上传相同 basename 但内容不同的同名文件 |
| 预期 | - 接受：生成新的 `id`<br>- 文件名 hash 不同，物理文件不冲突 |
| 选择器 | `a-mt-row` |
| 清理 | 删除新文件 |

### M-011：素材列表分页

| 项 | 内容 |
| ---- | ---- |
| 前置 | 临时上传 11 个 PDF |
| 步骤 | 1. 翻页 |
| 预期 | - 默认 size=10 |
| 选择器 | `a-mt-pagination` |
| 清理 | 删除临时文件 |

### M-012：素材下载文件可用

| 项 | 内容 |
| ---- | ---- |
| 前置 | M-001 |
| 步骤 | 1. 复制 `MAT_PDF_1` 的下载 URL<br>2. 直接 GET |
| 预期 | - 200，`Content-Type: application/pdf`<br>- 文件内容长度与本地 fixture 一致 |
| 选择器 | `a-mt-row` |
| 清理 | 无 |

### M-013：上传 PPTX 触发 LibreOffice 转 PDF

| 项 | 内容 |
| ---- | ---- |
| 前置 | 本地或容器已安装 LibreOffice（[setup-teardown §3](./setup-teardown.md)） |
| 步骤 | 1. 上传 `courseware-with-pptx-20slides.pptx`<br>2. 后端响应中确认 `previewPdfPath` 非空<br>3. 调 `GET /api/public/materials/{id}/stream` |
| 预期 | - 200 + `Content-Type: application/pdf`<br>- `Content-Disposition: inline; filename="<name>.pdf"`<br>- 物理文件路径下存在同名 `<safe_name>.pdf` |
| 选择器 | `a-mt-row[data-material-id]` |
| 清理 | 删除该素材 |

### M-014：上传损坏 PPTX 不阻断上传

| 项 | 内容 |
| ---- | ---- |
| 前置 | `corrupt.pptx`（10KB 随机字节，扩展名伪装）预置 |
| 步骤 | 1. 上传该文件<br>2. 观察列表与详情 |
| 预期 | - HTTP 200，上传成功<br>- `previewPdfPath` 为 NULL（LibreOffice 失败仅记 logger）<br>- 前台 P-VIEWER-PPT 进入后提示“预览生成中”，下载到本地仍可用 |
| 选择器 | `a-mt-row`, `p-viewer-ppt-preview-pending` |
| 清理 | 删除该素材 |

### M-015：删除 PPTX 同步清理预览 PDF

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PPT_1`（已转换）可被课件解绑 |
| 步骤 | 1. 解绑 `MAT_PPT_1` 关联<br>2. 删除 `MAT_PPT_1`<br>3. 检查物理目录 |
| 预期 | - 数据库 `preview_pdf_path` 同步清空<br>- 物理 `<safe_name>.pdf` 被删除 |
| 选择器 | `a-mt-row` |
| 清理 | 无 |

### M-016：公开素材流式接口 disposition 与 Content-Type

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已上传 `MAT_VIDEO_1` / `MAT_PDF_1` / `MAT_PPT_1` |
| 步骤 | 1. 调 `GET /api/public/materials/{MAT_VIDEO_1}/stream`<br>2. 调 `GET /api/public/materials/{MAT_PDF_1}/stream`<br>3. 调 `GET /api/public/materials/{MAT_PPT_1}/stream`（已转换）<br>4. 调 `GET /api/public/materials/{MAT_PPT_2}/stream`（`preview_pdf_path = NULL`，兜底） |
| 预期 | - VIDEO：200 + `Content-Type: video/mp4` + `Content-Disposition: inline`<br>- PDF：200 + `Content-Type: application/pdf` + `Content-Disposition: inline`<br>- PPT 已转换：200 + `Content-Type: application/pdf` + `Content-Disposition: inline; filename="<name>.pdf"`<br>- PPT 未转换：200 + `Content-Type: application/octet-stream` + `Content-Disposition: attachment; filename="<name>.pptx"` |
| 选择器 | （无，curl 验证） |
| 清理 | 无 |

### M-017：公开素材流式接口 60/min/ip 限流

| 项 | 内容 |
| ---- | ---- |
| 前置 | 任一素材 |
| 步骤 | 1. 连续 60 次调用 `/api/public/materials/{id}/stream`<br>2. 第 61 次观察 |
| 预期 | - 第 61 次起 HTTP 429 `rate_limited`（[10 §5.2.4](../spec/10-API设计规范.md)） |
| 选择器 | （无，curl 验证） |
| 清理 | 等待 1 分钟 |

### M-018：公开素材单条接口

| 项 | 内容 |
| ---- | ---- |
| 前置 | `MAT_PPT_1` 已转换 |
| 步骤 | 1. 调 `GET /api/public/materials/{MAT_PPT_1}` |
| 预期 | - 200，返回 `{id, name, type, streamUrl, downloadUrl, sizeBytes, duration, previewReady}`<br>- 响应中**不**包含 `storagePath`（[10 §5.2.3](../spec/10-API设计规范.md)）<br>- `previewReady = true`（`preview_pdf_path` 非 NULL）<br>- 调 `MAT_PPT_2`（未转换）：`previewReady = false` |
| 选择器 | （无，curl 验证） |
| 清理 | 无 |

### M-019：素材不存在返 404

| 项 | 内容 |
| ---- | ---- |
| 前置 | 无 |
| 步骤 | 1. 调 `GET /api/public/materials/999999` |
| 预期 | - 404 `material_not_found` |
| 选择器 | （无，curl 验证） |
| 清理 | 无 |

---

## 4. Token 管理（A-TK-LIST）

### TKN-001：Token 列表渲染

| 项 | 内容 |
| ---- | ---- |
| 前置 | Setup 完成 + 登录 |
| 步骤 | 1. 导航至 `/admin/tokens` |
| 预期 | - 3 行：`TKN_A 产品组·Q3`, `TKN_B 研发组·Q3`, `TKN_C 仅 Java 组`<br>- 关联课件数列：`TKN_A = 1`, `TKN_B = 1`, `TKN_C = 1` |
| 选择器 | `a-tk-row`, `a-tk-count-cell` |
| 清理 | 无 |

### TKN-007a：关联课件数列动态更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-001 |
| 步骤 | 1. 记录初始 `关联课件数`（TKN_A=1, TKN_B=1, TKN_C=1）<br>2. 创建一个临时课件 `CW_FOR_TKN_COUNT`，绑定 `TKN_A`<br>3. 刷新 Token 列表<br>4. 删除 `CW_FOR_TKN_COUNT` 并刷新 |
| 预期 | - 步骤 3 后 `TKN_A` 的 `关联课件数` 变为 `2`<br>- `TKN_B, TKN_C` 不变（仍为 1）<br>- 步骤 5 后 `TKN_A` 恢复为 `1`<br>- 数字与 `courseware_access_token` 实时计算一致（[05 §6 派生字段](../spec/05-数据模型.md)） |
| 选择器 | `a-tk-row`, `a-tk-count-cell` |
| 清理 | 无 |

### TKN-002：搜索 Token

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-001 |
| 步骤 | 1. `[data-testid="a-tk-search-input"]` 输入 `产品` |
| 预期 | - 命中 `TKN_A`<br>- 其他不命中 |
| 选择器 | `a-tk-search-input`, `a-tk-row` |
| 清理 | 清空 |

### TKN-003：新建 Token 弹窗

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-001 |
| 步骤 | 1. 点击 `[data-testid="a-tk-new-btn"]`<br>2. 弹窗出现 |
| 预期 | - 弹窗含名称输入框、创建、取消<br>- `data-testid="a-tk-once-value"` **不**可见（未创建前） |
| 选择器 | `a-tk-new-btn`, `a-tk-new-label-input`, `a-tk-new-create-btn`, `a-tk-new-cancel-btn` |
| 清理 | 关闭弹窗 |

### TKN-004：新建 Token 成功并展示明文

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-003 |
| 步骤 | 1. 输入 `A-Token-测试`<br>2. 点击创建 |
| 预期 | - HTTP 200 `ok`<br>- 弹窗切换为"一次性明文展示"<br>- `[data-testid="a-tk-once-value"]` 出现，文本 = 16~32 字符的 token 原值<br>- 列表多 1 行<br>- 刷新后明文区域消失 |
| 选择器 | `a-tk-once-value`, `a-tk-copy-btn` |
| 清理 | 保存明文至测试上下文；删除该 Token |

### TKN-008a：新建 Token 名称为空被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-003 弹窗打开 |
| 步骤 | 1. 不输入名称（或仅输入空格）<br>2. 点击 `[data-testid="a-tk-new-create-btn"]` |
| 预期 | - 创建按钮 `disabled`（[08 §8 TKN-008](../spec/08-验收标准.md)）<br>- 若绕过前端提交，后端 400 `token_label_required`（[10 §3.2.6](../spec/10-API设计规范.md)）<br>- 错误文案`请输入令牌名称`<br>- 名称**必填且全局唯一**（业务规则 R-04b，详见 [05 §2.5](../spec/05-数据模型.md)）<br>- 列表不增加新行 |
| 选择器 | `a-tk-new-create-btn`, `a-tk-new-label-input`, `g-field-error` |
| 清理 | 关闭弹窗 |

### TKN-005：重新生成 Token（多 Token 课件）

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_A` 关联 `CW_RESTRICTED`（同时 `TKN_B` 也关联） |
| 步骤 | 1. 点击 `[data-testid="a-tk-regen-btn"]`（TKN_A）<br>2. 二次确认 `g-confirm-ok` |
| 预期 | - HTTP 200 `ok`<br>- 返回新的明文（与原 `TKN_A` 不同）<br>- 数据库 `value_hash` 更新<br>- `CW_RESTRICTED` 仍可访问（旧明文失效） |
| 选择器 | `a-tk-regen-btn`, `a-tk-once-value` |
| 清理 | 不再恢复；Teardown 时一并清理 |

### TKN-006：重新生成 Token（最后 Token 课件）

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_C` 仅关联 `CW_LAST_TOKEN` |
| 步骤 | 1. 点击 `[data-testid="a-tk-regen-btn"]`（TKN_C）<br>2. 二次确认 |
| 预期 | - HTTP 422 `last_token_required`<br>- 错误文案"该课件仅剩 1 个有效 Token，请先将课件转为开放模式" |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### TKN-007：删除 Token（多 Token 课件）

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_A` 关联 `CW_RESTRICTED`（还有 `TKN_B`） |
| 步骤 | 1. 点击 `[data-testid="a-tk-delete-btn"]`<br>2. 二次确认 |
| 预期 | - HTTP 200 `ok`<br>- `TKN_A` 消失<br>- `CW_RESTRICTED` 关联课件数 = 1（仅 `TKN_B`） |
| 选择器 | `a-tk-delete-btn`, `g-confirm-ok` |
| 清理 | 重新生成 `TKN_A`（v1.1+）或恢复 Setup |

### TKN-008：删除 Token（最后 Token 课件）

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TKN_C` 仅关联 `CW_LAST_TOKEN` |
| 步骤 | 1. 点击 `[data-testid="a-tk-delete-btn"]`<br>2. 二次确认 |
| 预期 | - HTTP 422 `last_token_required` |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### TKN-009：行内修改 label

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-001 |
| 步骤 | 1. 在 `TKN_A` 行点击编辑（`a-tk-label-input`）<br>2. 改为 `产品组·Q4`<br>3. 点击 `[data-testid="a-tk-label-save-btn"]` |
| 预期 | - HTTP 200 `ok`<br>- 列表 label 更新 |
| 选择器 | `a-tk-label-input`, `a-tk-label-save-btn` |
| 清理 | 恢复原 label |

### TKN-010：label 重复

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-001 |
| 步骤 | 1. 试图把 `TKN_B` 改名为 `产品组·Q3`（与 `TKN_A` 重复） |
| 预期 | - HTTP 409 `token_label_conflict`（[08 §8 TKN-003](../spec/08-验收标准.md) / [10 §3.2.6](../spec/10-API设计规范.md)）<br>- 错误文案`令牌名称已存在，请更换`<br>- 数据库中 `TKN_B` 的 label **不**变（拒接改名）<br>- 含空格 / 特殊符号重复同样被拒（[05 §2.5 R-04b](../spec/05-数据模型.md)） |
| 选择器 | `g-toast--error` |
| 清理 | 无 |

### TKN-011：label 为空被拒

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-009 |
| 步骤 | 1. 改为空字符串 |
| 预期 | - 前端禁用保存按钮 / 字段错误 |
| 选择器 | `a-tk-label-save-btn`, `g-field-error` |
| 清理 | 无 |

### TKN-012：label 超过 50 字符

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-009 |
| 步骤 | 1. 输入 51 字符 |
| 预期 | - 前端 maxlength 限制为 50 |
| 选择器 | `a-tk-label-input` |
| 清理 | 无 |

### TKN-013：复制明文按钮

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-004 创建后明文仍可见 |
| 步骤 | 1. 点击 `[data-testid="a-tk-copy-btn"]` |
| 预期 | - Clipboard 写入 token 明文<br>- 提示 `g-toast--success` "已复制" |
| 选择器 | `a-tk-copy-btn`, `g-toast--success` |
| 清理 | 无 |

### TKN-014：Token 列表分页

| 项 | 内容 |
| ---- | ---- |
| 前置 | 临时创建 11 个 Token |
| 步骤 | 1. 翻页 |
| 预期 | - 默认 size=10 |
| 选择器 | `a-tk-pagination` |
| 清理 | 删除临时 Token |

### TKN-015：Token 明文一次性展示后刷新消失

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-004 |
| 步骤 | 1. 弹窗切到列表后再回来 |
| 预期 | - 明文不可再获取（弹窗不展示）<br>- 数据库 `value_hash` 不变 |
| 选择器 | `a-tk-once-value` |
| 清理 | 无 |

### TKN-016：删除 Token 后课件自动解绑

| 项 | 内容 |
| ---- | ---- |
| 前置 | TKN-005 / TKN-007 操作后 |
| 步骤 | 1. 切换到课件管理<br>2. 观察 `CW_RESTRICTED` 关联课件数 |
| 预期 | - 课件中 `accessTokenIds` 已不含已删 Token |
| 选择器 | `a-cw-row`, `a-cw-access-cell` |
| 清理 | 无 |

---

## 5. 跨模块一致性

### X-010：课件删除 → Token 关联课件数更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | A-133 验证场景 |
| 步骤 | 1. 删除 `CW_RESTRICTED`<br>2. 切到 Token 管理 |
| 预期 | - `TKN_A, TKN_B` 关联课件数 = 0 |
| 选择器 | `a-tk-row`, `a-tk-count-cell` |
| 清理 | 重新 Setup 或恢复 |

### X-011：分类删除 → 课件受影响

| 项 | 内容 |
| ---- | ---- |
| 前置 | C-008 场景 |
| 步骤 | 1. 试图删除 `入门`（已含 `CW_OPEN_BASIC`） |
| 预期 | - 后端拒绝<br>- 课件列表仍可访问 |
| 选择器 | `a-cw-row` |
| 清理 | 无 |

### X-012：素材删除 → 课件素材列表更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | 已创建 `CW_TEMP` 关联 `MAT_VIDEO_TEST` |
| 步骤 | 1. 删除 `MAT_VIDEO_TEST`<br>2. 编辑 `CW_TEMP` |
| 预期 | - 编辑表单中"已关联"区域不再显示 `MAT_VIDEO_TEST`<br>- 数据库 `material_ids` 中该项被清空 |
| 选择器 | `a-cw-mat-linked-item` |
| 清理 | 删除 `CW_TEMP` |

### X-013：Tag 删除 → 课件引用清理

| 项 | 内容 |
| ---- | ---- |
| 前置 | T-007 场景 |
| 步骤 | 1. 试图删除 `TAG_PM`（关联 2 个课件） |
| 预期 | - 后端拒绝<br>- 课件中 `tag_ids` 仍含 `TAG_PM` |
| 选择器 | `a-cw-row` |
| 清理 | 无 |

### X-002a：端到端：标签解绑后前台搜索更新

| 项 | 内容 |
| ---- | ---- |
| 前置 | `TAG_AGILE` 关联 `CW_OPEN_MULTI`；前端 `coursewareTokens` 为空 |
| 步骤 | 1. 前台访问 `{BASE}/result?q=Scrum`，命中 `CW_OPEN_MULTI`<br>2. 后台访问 `/admin/tags`，选中 `TAG_AGILE` 记录 `关联课件数`（= 1）<br>3. 后台编辑 `CW_OPEN_MULTI`，取消勾选 `TAG_AGILE` 后保存<br>4. 前台刷新 `{BASE}/result?q=Scrum` |
| 预期 | - 步骤 1：`CW_OPEN_MULTI` 出现（[08 §10 X-002](../spec/08-验收标准.md)）<br>- 步骤 2：`TAG_AGILE` 关联课件数 = 1<br>- 步骤 3：保存成功，HTTP 200 `ok`<br>- 步骤 4：`CW_OPEN_MULTI` 仍可被搜索到（[05 §R-08](../spec/05-数据模型.md)）<br>- 步骤 4 后：`TAG_AGILE` 关联课件数 = 0；列表中 `CW_OPEN_MULTI` 的 `tag_ids` 不再含 `TAG_AGILE` |
| 选择器 | `a-tg-row`, `a-tg-count-cell`, `p-result-card` |
| 清理 | 恢复 `CW_OPEN_MULTI` 与 `TAG_AGILE` 的关联 |

---

## 6. 用例与数据关系矩阵

| 用例 | 关键数据 |
| ---- | -------- |
| C-001 ~ C-012 | 全部 8 个分类 |
| T-001 ~ T-012 | 5 个标签 |
| M-001 ~ M-012 | 4 个素材 |
| TKN-001 ~ TKN-016, TKN-007a, TKN-008a | 3 个 Token + 课件关联 |
| X-010 ~ X-013, X-002a | 全部 4 个课件 |

---

## 7. 用例覆盖矩阵

| 文档章节 | 用例 ID |
| -------- | ------- |
| [04 §4 分类管理](../spec/04-管理后台规格.md) | C-001 ~ C-012 |
| [04 §5 标签管理](../spec/04-管理后台规格.md) | T-001 ~ T-012 |
| [04 §6 素材管理](../spec/04-管理后台规格.md) | M-001 ~ M-019 |
| [04 §7 Token 管理](../spec/04-管理后台规格.md) | TKN-001 ~ TKN-016, TKN-007a, TKN-008a |
| [08 A03](../spec/08-验收标准.md) | C-001 ~ C-012 |
| [08 A04](../spec/08-验收标准.md) | T-001 ~ T-012 |
| [08 A05](../spec/08-验收标准.md) | M-001 ~ M-019 |
| [08 A06](../spec/08-验收标准.md) | TKN-001 ~ TKN-016, TKN-007a, TKN-008a |
| [08 §10 X-002](../spec/08-验收标准.md) | X-002a |
| [05 §R-12](../spec/05-数据模型.md) | TKN-006, TKN-008, A-127, A-140 |
| [08 M-009 / M-010](../spec/08-验收标准.md) | M-013, M-014 |
| [10 §5.2.3 / §5.2.4](../spec/10-API设计规范.md) | M-016, M-017, M-018, M-019 |
