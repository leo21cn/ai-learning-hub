---
kind: dependency_management
name: 依赖管理：Python Poetry + npm lockfile 双轨锁定
category: dependency_management
scope:
    - '**'
source_files:
    - backend/pyproject.toml
    - frontend/package.json
    - frontend/package-lock.json
    - package.json
---

## 1. 使用的系统/方法
- **后端（Python）**：使用 **Poetry** 作为包管理器与构建系统，通过 `backend/pyproject.toml` 声明运行时依赖与可选开发依赖，构建后端镜像时由 `poetry-core` 驱动安装。
- **前端（Node.js）**：使用 **npm**，通过 `frontend/package.json` 声明依赖，并配套提交 `frontend/package-lock.json`（lockfileVersion=3）以固定完整依赖树。
- **根级 package.json**：仓库根仅保留一个最小 `package.json`，只声明 `pdfjs-dist` 供脚本/工具链使用，不参与应用构建。
- **无 vendoring / 私有源**：未发现 `requirements.txt`、`Pipfile`、`setup.py`、`vendor/` 目录或任何自定义 PyPI 源配置；所有 Python 包均从默认 PyPI 拉取。前端也未见 `.npmrc` 等私有源配置。

## 2. 关键文件与位置
- `backend/pyproject.toml` — 后端项目元数据、运行依赖、可选依赖、Ruff/pytest 配置及 Poetry 构建后端声明。
- `frontend/package.json` — 前端应用依赖与脚本入口（dev/build/test:e2e 等）。
- `frontend/package-lock.json` — 前端依赖的精确快照，确保 CI/本地/容器内一致安装。
- `package.json`（仓库根）— 顶层轻量依赖，仅用于脚本侧工具。

## 3. 架构与约定
- **版本策略**
  - 后端：对核心库采用**精确版本锁定**（如 `fastapi==0.115.5`、`uvicorn[standard]==0.32.1`、`sqlalchemy[asyncio]==2.0.36`），避免上游破坏性升级影响生产。
  - 前端：对业务与框架依赖使用**语义化范围**（`^x.y.z`），在保持兼容性的前提下允许小版本演进，并由 lockfile 固化实际解析结果。
- **依赖分层**
  - 后端通过 `[project.optional-dependencies] dev = [...]` 将测试与代码质量工具（pytest、ruff、mypy）与运行时代码解耦，Docker 镜像仅安装 `--no-dev` 下的依赖。
  - 前端通过 `dependencies` / `devDependencies` 区分运行期与构建期依赖，构建产物不包含开发工具。
- **可复现构建**
  - 前端通过 `package-lock.json` 保证多环境一致；后端虽未提交 `poetry.lock`，但通过 pyproject 中的精确版本号实现等价的可复现效果。
- **容器集成**
  - 后端 Dockerfile 基于 `python:3.11-slim`，通过 Poetry 安装依赖；前端 Dockerfile 基于 Node 镜像，通过 `npm ci --only=production` 安装依赖，二者均遵循“只安装必要依赖”的原则。

## 4. 开发者应遵守的规则
- **新增依赖**
  - 后端：在 `backend/pyproject.toml` 的 `dependencies` 中声明，优先使用 `==` 精确版本；若仅为开发用途，放入 `[project.optional-dependencies] dev`。
  - 前端：在 `frontend/package.json` 对应字段中添加，并通过 `npm install` 更新 `package-lock.json`，禁止手动编辑 lockfile。
- **升级依赖**
  - 后端：谨慎升级精确版本，升级后需同步更新相关测试与类型检查。
  - 前端：使用 `npm update` 或指定范围升级，确认 lockfile 变更后重新跑 `test:e2e`。
- **私有源/代理**
  - 当前未配置任何私有源；如需引入内部包，应在各自模块的 `.npmrc` 或 Poetry 的 `[[tool.poetry.source]]` 中集中配置，并在团队内统一文档说明。
- **镜像构建**
  - 不要将 `node_modules` 或 `.venv` 打入镜像；始终通过各自的包管理器在镜像构建阶段安装依赖，以保证镜像体积与安全扫描一致性。