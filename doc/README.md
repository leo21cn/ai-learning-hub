# Learning Hub 文档中心

> 本目录是 Learning Hub 项目的**唯一文档中心**，存放项目规格、测试、部署与专项改造计划。
> 与代码同仓存放，规格变化时 PR 须同步更新对应章节。
>
> **文档版本**：v1.2 — 与 [doc/spec v1.2](./spec/README.md) 同步。
> **生成日期**：2026-07-07

---

## 1. 一句话定位

**Learning Hub** 是一个以"AI 智能搜索"为核心入口的企业学习资料门户。本目录沉淀了项目自 v1.0 反向工程梳理起的全部产品、测试与部署文档，并对每次规格演进（含本轮 v1.2 素材在线浏览改造）保持同步更新。

---

## 2. 目录结构

```text
doc/
├── README.md            ← 本文件：文档总索引与导航
├── spec/                ← 产品规格说明书（10 章 + 总览）
│   ├── README.md
│   ├── 01-产品概述.md
│   ├── 02-功能需求.md
│   ├── 03-前台门户规格.md
│   ├── 04-管理后台规格.md
│   ├── 05-数据模型.md
│   ├── 06-非功能需求.md
│   ├── 07-技术架构.md
│   ├── 08-验收标准.md
│   ├── 09-UI规格.md
│   └── 10-API设计规范.md
├── test/                ← 测试用例（Browser Agent 就绪）
│   ├── README.md
│   ├── selectors.md
│   ├── setup-teardown.md
│   ├── test-data.md
│   ├── test-cases-front.md
│   ├── test-cases-admin.md
│   ├── test-cases-mgmt.md
│   └── test-cases-integration.md
├── deploy/              ← ECS / Docker Swarm 部署指南（详细）
│   └── README.md
└── plans/               ← （预留）专项改造计划归档（v1.2+ 暂由 Qoder 规划文件承载）
```

> 与 `deploy/README.md`（仓库根目录）的分工：`doc/deploy/README.md` 是**详细**部署指南（含 nginx vhost、Swarm 网络、持久化方案等），根目录 `deploy/README.md` 是**快速开始 / Smoke 验证**入口。

---

## 3. 文档导航表

| 类别 | 文档 | 用途 | 阶段 |
| ---- | ---- | ---- | ---- |
| 规格 | [doc/spec/README.md](./spec/README.md) | 10 章规格总览与目录索引 | 全周期 |
| 规格 | [doc/spec/01-产品概述.md](./spec/01-产品概述.md) | 产品定义、目标用户、术语表 | v1.0~v1.2 |
| 规格 | [doc/spec/02-功能需求.md](./spec/02-功能需求.md) | 功能清单 F01~F07（v1.2 新增 F01.08） | v1.0~v1.2 |
| 规格 | [doc/spec/03-前台门户规格.md](./spec/03-前台门户规格.md) | 前台门户页面、交互、状态（v1.2 新增 §5a P-VIEWER） | v1.0~v1.2 |
| 规格 | [doc/spec/04-管理后台规格.md](./spec/04-管理后台规格.md) | 后台各模块页面与流程（v1.2 素材上传降级说明） | v1.0~v1.2 |
| 规格 | [doc/spec/05-数据模型.md](./spec/05-数据模型.md) | 实体、字段、关系、生命周期（v1.2 新增 `preview_pdf_path`） | v1.0~v1.2 |
| 规格 | [doc/spec/06-非功能需求.md](./spec/06-非功能需求.md) | 性能、安全、可用性、兼容性（v1.2 补 PPT 转 PDF 60s 超时） | v1.0~v1.2 |
| 规格 | [doc/spec/07-技术架构.md](./spec/07-技术架构.md) | 技术栈与部署形态（v1.2 补 LibreOffice 节点 + 数据流） | v1.0~v1.2 |
| 规格 | [doc/spec/08-验收标准.md](./spec/08-验收标准.md) | 验收用例（v1.2 新增 AC-019~025、INT-V-001~003） | v1.0~v1.2 |
| 规格 | [doc/spec/09-UI规格.md](./spec/09-UI规格.md) | UI ↔ 业务实体矩阵与状态机（v1.2 新增 P-VIEWER-VIDEO/PDF/PPT） | v1.0~v1.2 |
| 规格 | [doc/spec/10-API设计规范.md](./spec/10-API设计规范.md) | 全量 HTTP API 契约（v1.2 新增 §5.2.3 / §5.2.4） | v1.0~v1.2 |
| 测试 | [doc/test/README.md](./test/README.md) | 测试文档总览、用例命名规范、Playwright 示例 | v1.0~v1.2 |
| 测试 | [doc/test/selectors.md](./test/selectors.md) | Browser Agent `data-testid` 规范（v1.2 新增 §3.5 P-VIEWER） | v1.0~v1.2 |
| 测试 | [doc/test/setup-teardown.md](./test/setup-teardown.md) | Setup / Teardown（v1.2 新增 §1.3 LibreOffice / PDF.js） | v1.0~v1.2 |
| 测试 | [doc/test/test-data.md](./test/test-data.md) | 测试数据 fixture（v1.2 新增 §4.1 PPT fixture 脚本） | v1.0~v1.2 |
| 测试 | [doc/test/test-cases-front.md](./test/cases-front.md) | 前台用例 F-*（v1.2 新增 §5a F-048~F-056） | v1.0~v1.2 |
| 测试 | [doc/test/test-cases-admin.md](./test/test-cases-admin.md) | 后台用例 A-*（v1.2 新增 §8 AD-180~183） | v1.0~v1.2 |
| 测试 | [doc/test/test-cases-mgmt.md](./test/test-cases-mgmt.md) | 后台分类/标签/素材/Token（v1.2 新增 M-013~M-019） | v1.0~v1.2 |
| 测试 | [doc/test/test-cases-integration.md](./test/test-cases-integration.md) | 集成 / 受限课件 / 非功能（v1.2 新增 §6a INT-V-001~003） | v1.0~v1.2 |
| 部署 | [doc/deploy/README.md](./deploy/README.md) | ECS + Docker Swarm 详细部署指南（v0.2 新增 §7 素材预览依赖） | v0.1~v0.2 |
| 部署 | [deploy/README.md](../deploy/README.md) | 仓库根目录快速开始 / Smoke 验证（v1.2 新增 §7.8） | v1.0~v1.2 |
| 改造计划 | **课件页素材在线浏览改造计划**（v1.2） | Qoder 规划文件：`课件页素材在线浏览改造_81477959.md`，由 Qoder 会话管理；本轮 11/14 子任务已完成，全部规格 / 测试 / 部署文档已同步 | v1.2 |

---

## 4. 阅读建议

| 角色 | 推荐顺序 |
| ---- | -------- |
| 产品 / 业务方 | `01` → `03` / `04` 按需查阅 |
| 设计师 | `03` + `04`（页面级）+ `09`（UI 矩阵） |
| 后端开发 | `02` + `05` + `07` + `10` |
| 前端开发 | `03` + `04` + `09` + `10` |
| 测试工程师 | `08`（验收） → `test/` 全套 |
| 运维 / SRE | `07` + `doc/deploy/README.md` → `deploy/README.md` |

---

## 5. 文档同步约定

1. **规格变更流程**：任何代码 PR 涉及规格变化时，**必须**同步更新 `doc/spec/` 对应章节，并在 `doc/spec/README.md §6` 修订记录表中追加一行（含版本号 / 日期 / 变更条目）。
2. **测试同步**：规格新增验收项时，必须在 `doc/test/selectors.md` 新增对应 `data-testid`，并在 `doc/test/test-cases-*.md` 内补齐用例，更新 `doc/test/README.md §4` 映射表。
3. **部署同步**：新增系统依赖（如本轮 LibreOffice）必须更新 `doc/deploy/README.md` 与 `deploy/README.md` 两份部署文档，并在本文件 §3 导航表中标注。
4. **改造计划归档**：Qoder 会话生成的 plan 文件会作为规格变更的"前置草案"，落地后转入本文件 §3 导航表 + 各章节的修订记录。

---

## 6. 变更记录

| 版本 | 日期 | 变更摘要 |
| ---- | ---- | -------- |
| 1.2 | 2026-07-07 | 新增素材在线浏览能力（PPT 幻灯片 / PDF Word / MP4 流媒体）<br>· 新增 §3 文档导航表中"课件页素材在线浏览改造计划"条目<br>· 同步全量 [doc/spec/](./spec/)（10 章 + README）至 v1.2；详见 [doc/spec/README.md §6 v1.2](./spec/README.md)<br>· 同步全量 [doc/test/](./test/)（8 份文档）至 v1.2；详见 [doc/test/README.md §8 v1.1](./test/README.md)<br>· 同步两份部署文档至 v1.2（[doc/deploy/README.md](./deploy/README.md) v0.2 / [deploy/README.md](../deploy/README.md) §7.8）<br>· 后端代码新增 `ppt_to_pdf` 服务、Material.preview_pdf_path 字段、`/api/public/materials/{id}/stream` 接口；前端代码新增 `P-VIEWER` 预览页（VIDEO / PDF / PPT 三种子组件），引入 `pdfjs-dist ^4.7.76`<br>· 测试代码新增 `backend/tests/test_materials_stream.py`、`frontend/e2e/front-viewer.spec.ts`、`frontend/e2e/fixtures/pptx-20slides.py` |
| 1.0 | 2026-07-06 | 首次建立 `doc/` 总索引，整合 `doc/spec/` v1.0 规格、`doc/test/` v1.0 测试文档、`doc/deploy/` v0.1 部署骨架 |

---

> 反馈与修订：本目录随代码同步演进，任何与代码行为不一致之处，以代码为准，并提交文档修订 PR。