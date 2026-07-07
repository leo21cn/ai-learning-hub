# 测试准备（Setup）与测试还原（Teardown）

> 本文件定义测试执行前后的**环境与数据**操作；每条步骤均为 Browser Agent 或运维脚本可执行的指令。
> 所有步骤顺序：Setup **自下而上**（先建依赖项再建被依赖项），Teardown **自上而下**（先删课件再删底层依赖）。

---

## 1. 测试环境前置（前置，**每次**测试前必做）

### 1.1 服务可达性

| 步骤 | 命令 / 行为 | 预期 |
| ---- | ----------- | ---- |
| 1.1.1 | `GET {BASE}/api/public/coursewares?page=1&size=1` | 200，`code: "ok"` |
| 1.1.2 | `GET {BASE}/api/health` | 200，`status: "UP"` |
| 1.1.3 | `GET {BASE}/admin` | 200，HTML 正常返回 |

### 1.2 基础存储与文件

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| 1.2.1 | ECS 上执行 `docker exec -it $(docker ps -qf name=learning-hub) ls /app/storage/documents/` | 目录存在（首次部署为空） |
| 1.2.2 | 上传 [test-data §4](./test-data.md) 列举的 `test/fixtures/*` 文件至 `/app/storage/documents/` | `scp -P 22 fixtures/* root@ecs:/app/storage/documents/` |
| 1.2.3 | `docker exec -it $(docker ps -qf name=learning-hub) chown -R app:app /app/storage/documents` | 应用进程可读写 |
| 1.2.4 | `docker exec -it $(docker ps -qf name=postgres) psql -U hub -d hub -c "SELECT 1;"` | 1 行返回 |

### 1.3 本地系统依赖（LibreOffice / PDF.js worker）

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| 1.3.1 | 容器内：`docker exec -it $(docker ps -qf name=learning-hub) which libreoffice` | 返回路径（如 `/usr/bin/libreoffice`），确认 [07 §2.1](../spec/07-技术架构.md) 选型已生效 |
| 1.3.2 | 容器内：`docker exec -it $(docker ps -qf name=learning-hub) libreoffice --version` | 版本号 ≥ 7.x（impress + core 子包足够） |
| 1.3.3 | 本地开发（Windows / Mac）：`which libreoffice` 或 `where libreoffice` | 不为空；macOS 使用 `brew install --cask libreoffice`；Windows 使用 `choco install libreoffice` |
| 1.3.4 | 前端静态产物：`ls frontend/dist/pdf.worker.min.mjs` | 文件存在；大小 > 100KB（验证 [03 §5a](../spec/03-前台门户规格.md) PDF.js 已正确打包） |
| 1.3.5 | 部署 nginx：`curl -I http://localhost/pdf.worker.min.mjs` | 200，与 INT-V-002 一致 |

### 1.4 浏览器

| 项 | 值 |
| ---- | ---- |
| Chrome | 127.x 或更高（含 DevTools / Network 调试） |
| 视口 | 1440×900（默认） / 768×1024 / 375×667（响应式用例切换） |
| 语言 | `zh-CN` |
| 时区 | `Asia/Shanghai` |

---

## 2. 预置素材文件（运行 Setup 前必做）

> 这些文件本身不入 git；首次跑测试需手工上传到 ECS，再让 Setup 调用后端 API 上传记录。

| 源路径（本地） | 目标路径（ECS） | 用途 |
| -------------- | --------------- | ---- |
| `test/fixtures/pm-intro-101.mp4` | `/app/storage/documents/pm-intro-101.mp4` | 视频素材 |
| `test/fixtures/scrum-guide.pdf` | `/app/storage/documents/scrum-guide.pdf` | PDF 素材 |
| `test/fixtures/java-backend.pptx` | `/app/storage/documents/java-backend.pptx` | PPT 素材 |
| `test/fixtures/legacy.ppt` | `/app/storage/documents/legacy.ppt` | 旧版 PPT |
| `test/fixtures/oversize.mp4` | `/app/storage/documents/oversize.mp4` | 200MB+ 视频，仅 M-003 用 |
| `test/fixtures/notallowed.exe` | `/app/storage/documents/notallowed.exe` | 非法扩展名，仅 M-004 用 |
| `test/fixtures/courseware-with-pptx-20slides.pptx` | `/app/storage/documents/courseware-with-pptx-20slides.pptx` | 20 页 PPTX（F-050/F-053 用例）；由 `scripts/gen_pptx_fixtures.py` 生成 |
| `test/fixtures/courseware-with-pptx-1slide.pptx` | `/app/storage/documents/courseware-with-pptx-1slide.pptx` | 1 页 PPTX（验证首末页 `disabled` 状态） |
| `test/fixtures/corrupt.pptx` | `/app/storage/documents/corrupt.pptx` | 损坏 PPTX，仅 M-014 用 |

> 文件名与 [test-data §4](./test-data.md) 表格一一对应；Setup 阶段调 `POST /api/admin/materials/upload` 时复用相同 basename。

---

## 3. 测试准备（Setup）— 顺序执行

> 浏览器/接口混合执行；每一步均使用 [test-data.md](./test-data.md) 中的固定值。
> 步骤 ID：`S-NN` 编号，Teardown 阶段反向执行 `TD-NN`。

### 3.1 浏览器与 localStorage 准备

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| S-01 | `await page.goto(BASE)` | 200 |
| S-02 | `await page.evaluate(() => localStorage.clear())` | localStorage 干净 |
| S-03 | `await page.goto(BASE + '/admin')` | 重定向至 `/admin/login` |
| S-04 | `await page.fill('[data-testid="a-login-token-input"]', 'demo')` | 输入成功 |
| S-05 | `await page.click('[data-testid="a-login-submit-btn"]')` | 进入 `/admin` |
| S-06 | `await expect(page.locator('[data-testid="a-nav-coursewares"]')).toBeVisible()` | 鉴权成功 |

### 3.2 分类种子（按层级顺序创建）

> 全部通过 `POST /api/admin/categories` 创建，参见 [10-API §3.2.2](../spec/10-API设计规范.md)。

| 步骤 | 请求体 | 记录 id | 期望返回 |
| ---- | ------ | ------- | -------- |
| S-10 | `{"name":"项目管理","parentId":null}` | `CAT_ROOT_PM` | `code: "ok"`，`data.id` |
| S-11 | `{"name":"软件工程","parentId":null}` | `CAT_ROOT_SE` | `code: "ok"`，`data.id` |
| S-12 | `{"name":"通用","parentId":"CAT_ROOT_PM"}` | `CAT_PM_GENERAL` | `code: "ok"` |
| S-13 | `{"name":"敏捷","parentId":"CAT_ROOT_PM"}` | `CAT_PM_AGILE` | `code: "ok"` |
| S-14 | `{"name":"后端","parentId":"CAT_ROOT_SE"}` | `CAT_SE_BE` | `code: "ok"` |
| S-15 | `{"name":"入门","parentId":"CAT_PM_GENERAL"}` | `CAT_PM_GENERAL_INTRO` | `code: "ok"` |
| S-16 | `{"name":"Scrum","parentId":"CAT_PM_AGILE"}` | `CAT_PM_AGILE_SCRUM` | `code: "ok"` |
| S-17 | `{"name":"Java","parentId":"CAT_SE_BE"}` | `CAT_SE_BE_JAVA` | `code: "ok"` |
| S-18 | 再次提交 `{"name":"项目管理","parentId":null}` | （不应创建） | `code: "category_name_conflict"`，HTTP 409 |

### 3.3 标签种子

| 步骤 | 请求体 | 记录 id | 期望返回 |
| ---- | ------ | ------- | -------- |
| S-20 | `{"name":"项目管理"}` | `TAG_PM` | `code: "ok"` |
| S-21 | `{"name":"敏捷"}` | `TAG_AGILE` | `code: "ok"` |
| S-22 | `{"name":"后端"}` | `TAG_BE` | `code: "ok"` |
| S-23 | `{"name":"入门"}` | `TAG_INTRO` | `code: "ok"` |
| S-24 | `{"name":"临时标签"}` | `TAG_TEMP` | `code: "ok"` |
| S-25 | `{"name":"项目管理"}`（重复） | - | `code: "tag_name_conflict"`，HTTP 409 |

### 3.4 素材种子

> 顺序：先上传文件，再调 `POST /api/admin/materials`，记录返回的 `id`。
> 文件已在 [§2](#2-预置素材文件运行-setup-前必做) 预置到 ECS。

| 步骤 | multipart 字段 | 请求体（额外） | 记录 id | 期望返回 |
| ---- | -------------- | -------------- | ------- | -------- |
| S-30 | `file=pm-intro-101.mp4` | `{"originalName":"pm-intro-101.mp4","type":"VIDEO"}` | `MAT_VIDEO_1` | `code: "ok"`，`data.id` |
| S-31 | `file=scrum-guide.pdf` | `{"originalName":"scrum-guide.pdf","type":"PDF"}` | `MAT_PDF_1` | `code: "ok"` |
| S-32 | `file=java-backend.pptx` | `{"originalName":"java-backend.pptx","type":"PPT"}` | `MAT_PPT_1` | `code: "ok"` |
| S-33 | `file=legacy.ppt` | `{"originalName":"legacy.ppt","type":"PPT"}` | `MAT_PPT_2` | `code: "ok"` |
| S-34 | `file=courseware-with-pptx-20slides.pptx` | `{"originalName":"courseware-with-pptx-20slides.pptx","type":"PPT"}` | `MAT_PPTX_20` | `code: "ok"`，`data.previewPdfPath` 非 NULL（LibreOffice 转换成功） |
| S-35 | `file=courseware-with-pptx-1slide.pptx` | `{"originalName":"courseware-with-pptx-1slide.pptx","type":"PPT"}` | `MAT_PPTX_1` | `code: "ok"` |

### 3.5 Token 种子

> 必须保留每个 Token 的明文原值到测试上下文，供 FTK-001 ~ FTK-007 用例引用。

| 步骤 | 请求体 | 记录 id | 期望返回 |
| ---- | ------ | ------- | -------- |
| S-40 | `{"label":"产品组·Q3"}` | `TKN_A` | `code: "ok"`，`data.value`（明文一次） |
| S-41 | `{"label":"研发组·Q3"}` | `TKN_B` | 同上 |
| S-42 | `{"label":"仅 Java 组"}` | `TKN_C` | 同上 |

### 3.6 课件种子

> 受限课件 R-12 约束：[05 §R-12](../spec/05-数据模型.md)，提交时 `accessTokenIds` 至少 1 项。

| 步骤 | 请求体 | 记录 id | 期望返回 |
| ---- | ------ | ------- | -------- |
| S-50 | `{"title":"项目管理入门","author":"张三","description":"面向新员工的项目管理基础课程。","categoryId":"CAT_PM_GENERAL_INTRO","tagIds":["TAG_PM","TAG_INTRO"],"materialIds":["MAT_VIDEO_1"],"accessMode":"OPEN","accessTokenIds":[]}` | `CW_OPEN_BASIC` | `code: "ok"` |
| S-51 | `{"title":"Scrum 实践指南","author":"张三","description":"Scrum 框架实践。","categoryId":"CAT_PM_AGILE_SCRUM","tagIds":["TAG_PM","TAG_AGILE"],"materialIds":["MAT_VIDEO_1","MAT_PDF_1"],"accessMode":"OPEN","accessTokenIds":[]}` | `CW_OPEN_MULTI` | `code: "ok"` |
| S-52 | `{"title":"Java 后端工程实践","author":"李四","description":"面向 Java 后端工程师的进阶培训材料。","categoryId":"CAT_SE_BE_JAVA","tagIds":["TAG_BE"],"materialIds":["MAT_PPT_1"],"accessMode":"RESTRICTED","accessTokenIds":["TKN_A","TKN_B"]}` | `CW_RESTRICTED` | `code: "ok"` |
| S-53 | `{"title":"内部培训（仅研发可见）","author":"王五","description":"仅研发组可见。","categoryId":"CAT_SE_BE_JAVA","tagIds":["TAG_BE"],"materialIds":["MAT_PPT_2"],"accessMode":"RESTRICTED","accessTokenIds":["TKN_C"]}` | `CW_LAST_TOKEN` | `code: "ok"` |

### 3.7 Setup 校验

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| S-60 | `GET /api/admin/categories?tree=true` | 树形结构含全部 8 个分类 |
| S-61 | `GET /api/admin/tags?page=1&size=100` | 5 行（`TAG_PM/AGILE/BE/INTRO/TEMP`） |
| S-62 | `GET /api/admin/materials?page=1&size=100` | 4 行 |
| S-63 | `GET /api/admin/tokens?page=1&size=100` | 3 行 |
| S-64 | `GET /api/admin/coursewares?page=1&size=100` | 4 行（`CW_OPEN_BASIC/OPEN_MULTI/RESTRICTED/LAST_TOKEN`） |
| S-65 | `GET /api/public/coursewares/search?keyword=项目管理&page=1&size=10` | 命中 `CW_OPEN_BASIC`（受限课件不出现） |

---

## 4. 测试还原（Teardown）— 反向执行

> 反向原则：先删课件，再删 Token / 标签 / 素材，最后删分类（叶子 → 根）。
> 任何步骤失败必须记录到 `.teardown-errors.log`，**不**阻塞后续步骤。

### 4.1 删除课件

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-10 | `DELETE /api/admin/coursewares/CW_OPEN_BASIC` | `code: "ok"`，HTTP 200 |
| TD-11 | `DELETE /api/admin/coursewares/CW_OPEN_MULTI` | `code: "ok"` |
| TD-12 | `DELETE /api/admin/coursewares/CW_RESTRICTED`（关联 `TKN_A` `TKN_B`） | `code: "ok"`，自动解绑 |
| TD-13 | `DELETE /api/admin/coursewares/CW_LAST_TOKEN` | `code: "ok"`，自动解绑 |
| TD-14 | 重复 `DELETE /api/admin/coursewares/CW_OPEN_BASIC` | `code: "courseware_not_found"`，HTTP 404 |

### 4.2 删除 Token

> 课件已全部删除，Token 可全部删除。

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-20 | `DELETE /api/admin/tokens/TKN_A` | `code: "ok"` |
| TD-21 | `DELETE /api/admin/tokens/TKN_B` | `code: "ok"` |
| TD-22 | `DELETE /api/admin/tokens/TKN_C` | `code: "ok"` |
| TD-23 | 重复 `DELETE /api/admin/tokens/TKN_A` | `code: "token_not_found"`，HTTP 404 |

### 4.3 删除素材

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-30 | `DELETE /api/admin/materials/MAT_VIDEO_1` | `code: "ok"` |
| TD-31 | `DELETE /api/admin/materials/MAT_PDF_1` | `code: "ok"` |
| TD-32 | `DELETE /api/admin/materials/MAT_PPT_1` | `code: "ok"` |
| TD-33 | `DELETE /api/admin/materials/MAT_PPT_2` | `code: "ok"` |
| TD-34 | `GET /api/admin/materials?page=1&size=10` | 0 行 |
| TD-35 | `docker exec -it postgres psql ... -c "SELECT count(*) FROM documents"` | 0 |

### 4.4 删除标签

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-40 | `DELETE /api/admin/tags/TAG_PM` | `code: "ok"` |
| TD-41 | `DELETE /api/admin/tags/TAG_AGILE` | `code: "ok"` |
| TD-42 | `DELETE /api/admin/tags/TAG_BE` | `code: "ok"` |
| TD-43 | `DELETE /api/admin/tags/TAG_INTRO` | `code: "ok"` |
| TD-44 | `DELETE /api/admin/tags/TAG_TEMP` | `code: "ok"` |

### 4.5 删除分类（叶子 → 根）

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-50 | `DELETE /api/admin/categories/CAT_PM_GENERAL_INTRO` | `code: "ok"` |
| TD-51 | `DELETE /api/admin/categories/CAT_PM_AGILE_SCRUM` | `code: "ok"` |
| TD-52 | `DELETE /api/admin/categories/CAT_SE_BE_JAVA` | `code: "ok"` |
| TD-53 | `DELETE /api/admin/categories/CAT_PM_GENERAL` | `code: "ok"` |
| TD-54 | `DELETE /api/admin/categories/CAT_PM_AGILE` | `code: "ok"` |
| TD-55 | `DELETE /api/admin/categories/CAT_SE_BE` | `code: "ok"` |
| TD-56 | `DELETE /api/admin/categories/CAT_ROOT_PM` | `code: "ok"` |
| TD-57 | `DELETE /api/admin/categories/CAT_ROOT_SE` | `code: "ok"` |
| TD-58 | 重复 `DELETE /api/admin/categories/CAT_ROOT_PM` | `code: "category_not_found"`，HTTP 404 |

### 4.6 清理 localStorage 与浏览器

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-60 | `await page.evaluate(() => localStorage.clear())` | localStorage 干净 |
| TD-61 | `await page.context().clearCookies()` | Cookie 清除 |
| TD-62 | `await page.close()` | 浏览器实例销毁 |

### 4.7 清理存储文件（可选，节省磁盘）

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-70 | `docker exec -it learning-hub rm -f /app/storage/documents/pm-intro-101.mp4` | - |
| TD-71 | `docker exec -it learning-hub rm -f /app/storage/documents/scrum-guide.pdf` | - |
| TD-72 | `docker exec -it learning-hub rm -f /app/storage/documents/java-backend.pptx` | - |
| TD-73 | `docker exec -it learning-hub rm -f /app/storage/documents/legacy.ppt` | - |

> **保留选项**：若 Teardown 后需要立即重跑 Setup，可跳过 §4.7；否则建议执行以释放磁盘。

### 4.8 还原校验

| 步骤 | 行为 | 预期 |
| ---- | ---- | ---- |
| TD-80 | `GET /api/public/coursewares?page=1&size=10` | `data.items` 为 `[]`（管理员课件清空） |
| TD-81 | `GET /api/admin/categories?tree=true` | `data.tree` 为 `[]` |
| TD-82 | `GET /api/admin/tags?page=1&size=100` | `data.total = 0` |
| TD-83 | `GET /api/admin/materials?page=1&size=100` | `data.total = 0` |
| TD-84 | `GET /api/admin/tokens?page=1&size=100` | `data.total = 0` |
| TD-85 | `docker exec -it postgres psql -c "SELECT count(*) FROM coursewares"` | 0 |
| TD-86 | `docker exec -it postgres psql -c "SELECT count(*) FROM access_tokens"` | 0 |
| TD-87 | `docker exec -it postgres psql -c "SELECT count(*) FROM documents"` | 0 |
| TD-88 | `docker exec -it postgres psql -c "SELECT count(*) FROM categories"` | 0 |
| TD-89 | `docker exec -it postgres psql -c "SELECT count(*) FROM tags"` | 0 |

---

## 5. 失败兜底

### 5.1 Setup 失败

- 任何 S-NN 步骤失败 → 终止 Setup → 自动触发 §4 全部 Teardown 步骤（保证测试环境干净）
- 在 `.setup-errors.log` 记录失败步骤、错误码、HTTP 状态

### 5.2 Teardown 失败

- 任何 TD-NN 步骤失败 → 记录到 `.teardown-errors.log` → **不**阻塞后续 TD 步骤
- 人工介入前不可再跑 Setup

### 5.3 用例执行期间失败

- 浏览器截图写入 `.artifacts/<case-id>.png`
- 网络请求历史写入 `.artifacts/<case-id>.network.json`
- 当前 `coursewareTokens` localStorage 值写入 `.artifacts/<case-id>.storage.json`

---

## 6. 幂等性

> Setup 阶段全部使用 `POST` + 显式幂等键缺失 → 重复执行 Setup 会因"重名"冲突失败。
> 因此：**Setup 仅在 Teardown 完成后**才允许重新执行。
> 若 Teardown 部分失败导致遗留，按 §5.2 流程先人工处理，再跑 Setup。
