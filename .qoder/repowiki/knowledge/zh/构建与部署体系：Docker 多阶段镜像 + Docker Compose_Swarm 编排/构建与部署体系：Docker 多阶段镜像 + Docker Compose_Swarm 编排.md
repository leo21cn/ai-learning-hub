---
kind: build_system
name: 构建与部署体系：Docker 多阶段镜像 + Docker Compose/Swarm 编排
category: build_system
scope:
    - '**'
source_files:
    - backend/Dockerfile
    - backend/entrypoint.sh
    - backend/pyproject.toml
    - frontend/Dockerfile
    - frontend/nginx.conf
    - deploy/local/docker-compose.yml
    - deploy/local/deploy-lh-local.ps1
    - deploy/ecs/compose.yml
    - deploy/ecs/publish.ps1
    - deploy/ecs/remote-setup.sh
    - deploy/ecs/db-init.sh
---

## 1. 构建系统概览

本项目采用 **容器优先** 的构建与发布策略，以 Docker 为统一边界，将后端（FastAPI/Python）、前端（React+Vite）和 Nginx 静态资源分别打包成独立镜像，再通过 Docker Compose（本地开发）与 Docker Swarm（ECS 生产）进行服务编排。顶层未使用 Makefile 或 CI YAML，而是通过 PowerShell 脚本串联各阶段的构建、打包、传输与部署。

- 后端依赖管理：`backend/pyproject.toml` 声明 Python 包版本；Dockerfile 内用 pip 直接安装（跳过 poetry lock 流程），保证构建可复现。
- 前端依赖管理：`frontend/package.json` + `package-lock.json`，通过 `npm ci` 在镜像中锁定版本。
- 数据库迁移：Alembic，随容器启动自动执行 `alembic upgrade head`。

## 2. 关键文件与职责

| 模块 | 核心文件 | 作用 |
|------|----------|------|
| 后端镜像 | `backend/Dockerfile` | 多阶段构建：python:3.11-slim → 安装 LibreOffice / ffmpeg / poppler-utils / CJK 字体等系统依赖 → pip 安装 Python 依赖 → 拷贝 app + alembic → HEALTHCHECK `/api/public/health` |
| 后端运行入口 | `backend/entrypoint.sh` | 等待 Postgres 可达 → 执行 `alembic upgrade head` → exec uvicorn 0.0.0.0:8000 |
| 后端配置 | `backend/pyproject.toml` | 定义项目名、Python>=3.11、依赖与 dev 工具集（pytest/ruff/mypy） |
| 前端镜像 | `frontend/Dockerfile` | node:20-alpine 构建 Vite 产物 → nginx:1.27-alpine 提供静态资源 + 反向代理 |
| 前端反向代理 | `frontend/nginx.conf` | SPA fallback、`/api/` 反代到 backend、大文件上传超时调至 600s、PDF.js worker MIME 修正 |
| 本地编排 | `deploy/local/docker-compose.yml` | 拉起 postgres/backend/frontend 三服务，含 healthcheck 与卷挂载 |
| 本地一键部署 | `deploy/local/deploy-lh-local.ps1` | 探测 Docker Desktop named pipe → compose build → up -d → 轮询 healthy → 验证 openapi 路由 |
| 生产编排 | `deploy/ecs/compose.yml` | Swarm v3.8 stack，复用外部 overlay 网络与 lh_storage volume，单副本 placement manager |
| 生产发布流水线 | `deploy/ecs/publish.ps1` | 读取 .env → docker buildx --platform linux/arm64 构建双镜像 → docker save → scp 到 ECS → ssh 触发 remote-setup/db-init/docker load/docker stack deploy → 轮询 Running → 调用 nginx-vhost-apply.sh 分两阶段签发证书并注入 443 server block → 持久化证书 mount |
| 远程初始化 | `deploy/ecs/remote-setup.sh` | 幂等创建 lh_storage volume 与工作目录 |
| 远程 DB 初始化 | `deploy/ecs/db-init.sh` | 查找 postgres 容器 → 幂等 CREATE DATABASE learning_hub |

## 3. 架构与约定

### 3.1 镜像分层与缓存
- 后端 Dockerfile 将系统依赖与 Python 依赖分层，利用 pip 缓存加速重复构建；首次构建因安装 LibreOffice/ffmpeg 约需 5–10 分钟。
- 前端 Dockerfile 先 COPY package*.json 再 npm install，利用 layer 缓存避免每次重建 node_modules。

### 3.2 跨平台交叉编译
- ECS 目标架构为 **linux/arm64**。publish.ps1 在 Windows x86 主机上通过 `docker buildx --platform linux/arm64` 完成交叉构建，默认复用 Docker Desktop QEMU 能力，无需额外 builder。

### 3.3 环境变量与配置注入
- 所有运行时配置通过 `.env` 文件集中管理（`deploy/ecs/.env`、`backend/.env.example`、`frontend/.env.example`），由 publish.ps1 解析后注入 SSH 远端环境变量。
- 后端通过 `pydantic-settings` 从环境变量加载配置；entrypoint.sh 用 shell 变量兜底默认值。

### 3.4 健康检查与服务发现
- 后端：Dockerfile 内置 HEALTHCHECK 探测 `/api/public/health`。
- 前端：compose 层覆盖 healthcheck，同时校验首页与 `/api/public/health`，确保 Nginx 反代链路正常。
- Swarm 下 frontend 通过 `learning-hub_backend` 服务 DNS 访问后端，publish.ps1 在构建前对 `nginx.conf` 做 sed 替换。

### 3.5 数据持久化
- 素材存储通过 `lh_storage` 命名卷挂载到 `/app/storage`，跨容器重启保留。
- PostgreSQL 数据卷 `pgdata` 在本地 compose 中持久化。

## 4. 开发者应遵循的规则

1. **新增 Python 依赖**：同步更新 `backend/pyproject.toml` 与 `backend/Dockerfile` 中的 pip install 行，保持两者一致。
2. **新增 Node 依赖**：更新 `frontend/package.json` 并提交 `package-lock.json`，确保 `npm ci` 可复现。
3. **修改 Nginx 反代目标**：仅改 `frontend/nginx.conf`；Swarm 环境由 publish.ps1 自动替换为 `learning-hub_backend`，无需维护两份配置。
4. **数据库变更**：新增 Alembic 迁移文件后，容器启动会自动执行 `upgrade head`；如需回滚，手动在 ECS 上执行 `alembic downgrade <rev>`。
5. **本地调试**：使用 `deploy/local/deploy-lh-local.ps1` 一键重建镜像并拉起服务，无需手动编写 docker-compose 命令。
6. **生产发布**：在 `deploy/ecs/.env` 填写真实凭据后执行 `publish.ps1`；若仅需热更应用镜像，加 `-SkipBuild`；若仅重新签发证书，加 `-SkipNginx`。
7. **大文件上传**：前后端均已将超时提升至 600s，勿在 Nginx 层自行降低限制。
8. **健康检查路径**：后端必须暴露 `/api/public/health`，否则 compose/swarm 健康检查会失败导致服务被标记 unhealthy。
