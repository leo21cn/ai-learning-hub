# Learning Hub 部署指南

> 本指南用于在阿里云 ECS 上的 Docker Swarm 集群中以 Stack 形式发布 `learning-hub` 应用，并复用已有的 `postgres` 与 `nginx-gateway` Stack 提供的服务。
>
> **文档状态**：骨架版（v0.1）—— 已记录关键背景信息，详细发布步骤待补充。
> **生成日期**：2026-07-06
> **目标环境**：ECS（公网）+ Docker Swarm
> **目标 Stack 名**：`learning-hub`
>
> ⚠️ **使用警告**：本文档当前**不建议直接用于生产部署**。待 §3 各小节补齐后方可作为可执行部署手册使用。详细优先级见 [§6 补齐优先级](#6-补齐优先级)。

---

## 1. 部署总览

```mermaid
graph TB
    Internet[公网用户] -->|HTTPS / 域名| ECS[ECS 公网 IP<br/>learning-hub.smartmoves.com.cn]
    ECS -->|443/80| Nginx[nginx-gateway Stack<br/>nginx 服务]
    Nginx -->|反向代理 /admin /api| App[learning-hub Stack<br/>Spring Boot 应用]
    App -->|复用外部网络| PgNet[(overlay / 已挂网络)]
    PgNet --> Postgres[postgres Stack<br/>postgres 服务]
    App --> Volume[(持久化卷<br/>素材 / 上传文件)]
```

### 1.1 一句话目标

将 `learning-hub` 应用以 Docker Stack 形式发布到 ECS 上现有的 Swarm 集群，复用同集群内已有的 `postgres`（数据库）和 `nginx-gateway`（反向代理 / HTTPS 终止）两个 Stack，仅在本 Stack 内承载应用本身的 Service。

---

## 2. 已知关键信息（已确认）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 部署平台 | 阿里云 ECS（Docker Swarm 集群） | 已加入现有 Swarm |
| Stack 名称 | `learning-hub` | `docker stack deploy -c docker-stack.yml learning-hub` |
| 公网域名 | `learning-hub.smartmoves.com.cn` | 已映射到 ECS 公网 IP |
| HTTPS 终止 | 由 `nginx-gateway` Stack 统一负责 | 本 Stack 不暴露 443 |
| 反向代理 | 复用 `nginx-gateway` Stack 下的 `nginx` 服务 | 本 Stack 通过该 nginx 转发到应用 Service |
| 数据库 | 复用 `postgres` Stack 下的 `postgres` Service | 本 Stack 不启动独立 DB |
| 数据库网络 | 复用 Swarm 已有的 overlay 网络（具体网络名待确认） | 与 `postgres` Service 同网络可达 |
| 端口约定 | 应用容器内部 8080 → 由 nginx-gateway 反向代理暴露 | 不直接对外 |

### 2.1 复用资源清单

| 复用对象 | 来源 Stack / 服务 | 复用方式 | 备注 |
| --- | --- | --- | --- |
| PostgreSQL | `postgres` Stack → `postgres` Service | 跨 Stack 通过 Swarm overlay 网络连接，使用既有数据库账号 / 数据库名 | 不在 `learning-hub` Stack 内创建 DB Service |
| Nginx 反向代理 | `nginx-gateway` Stack → `nginx` Service | 由该 nginx 配置中新增 `server_name learning-hub.smartmoves.com.cn` 的 vhost，上游指向 `learning-hub` Stack 的应用 Service | `learning-hub` Stack 仅声明 Service，不直接处理 TLS |

> ⚠️ 任何对复用资源的修改（如 nginx vhost、PG 数据库 / 账号）都不属于本 Stack 范畴，需另行评估。

---

## 3. 待补充内容（占位清单）

> 后续将逐步完善以下章节。每个章节完成时同步把"待补充"标记去掉，并升一档小版本号。

### 3.1 Stack 清单与镜像
- [ ] `learning-hub` Stack 内的 Service 列表（应用、迁移、监控……）
- [ ] 镜像来源（私有仓库 / 公共仓库）、镜像 Tag 约定
- [ ] 多副本 / 滚动更新策略

### 3.2 Swarm 网络与复用约束
- [ ] 与 `postgres` Service 通信所用的 overlay 网络名称
- [ ] 与 `nginx-gateway` 中 `nginx` Service 通信所用的 overlay 网络名称
- [ ] 是否需要在 `learning-hub` Stack 内 `external: true` 声明这些网络

### 3.3 数据库 / 缓存
- [ ] PostgreSQL 连接信息（主机名 / 端口 / 数据库 / 账号 / 密码来源）
- [ ] 数据库初始化（首次发布是否需要 Flyway / Liquibase / 自定义 SQL 迁移）
- [ ] 凭据注入方式（Docker secret / env / config）

### 3.4 配置与环境变量
- [ ] Spring Boot 配置项清单
- [ ] 必需的环境变量与默认值
- [ ] 敏感信息（Admin Token、JWT 密钥、LLM Key 等）的来源

### 3.5 持久化与文件存储
- [ ] 素材上传目录 (`/app/storage/documents`) 的 volume 挂载方案
- [ ] 是否引入对象存储（OSS / S3）替代本地卷
- [ ] 备份策略

### 3.6 Nginx vhost（nginx-gateway Stack 内）
- [ ] `learning-hub.smartmoves.com.cn` 的 server 块草案
- [ ] upstream 指向 `learning-hub` Stack 的哪个 Service
- [ ] HTTPS 证书复用方式（是否与其它站点共用 wildcard）
- [ ] 静态资源 / 大文件上传 / AI 搜索超时的反代参数

### 3.7 发布与回滚
- [ ] 首次部署步骤（`docker stack deploy` 前的准备）
- [ ] 版本更新 / 滚动发布流程
- [ ] 回滚步骤与数据兼容性注意事项
- [ ] 健康检查 / 探活策略

### 3.8 验证
- [ ] ECS 远程验证（**禁止本地验证**）
- [ ] 域名解析、HTTPS 证书、反代连通性逐项 checklist
- [ ] 前后台功能冒烟用例

---

## 4. 命名与约定（拟定，待确认）

| 维度 | 拟定值 | 备注 |
| --- | --- | --- |
| Stack 名 | `learning-hub` | 已确认 |
| 应用 Service 名 | `learning-hub-app`（建议） | 便于 nginx upstream 引用 |
| 镜像名 | `learning-hub/app:<tag>` | tag 约定见 3.1 |
| 持久卷名 | `learning-hub_storage` | bind / nfs / OSS 待定 |
| 配置文件名 | `docker-stack.yml`（或 `stack.yml`） | 仓库根目录 |
| 环境变量来源 | `.env.production` + Docker secret | 不入仓库 |

---

## 5. 不在本部署范围

- `postgres` Stack 的部署与运维（已有）
- `nginx-gateway` Stack 的部署与运维（已有）
- HTTPS 证书的申请与续签（统一在 `nginx-gateway` 内管理）
- 域名 DNS 解析（已映射到 ECS 公网 IP）

---

## 6. 补齐优先级

下列顺序供后续作者参考，确保文档先解决`能不能部署`再解决`部署得顺手`：

| 优先级 | 章节 | 阻塞项 |
| ------ | ---- | ------ |
| P0 | [§3.3 数据库 / 缓存](./README.md) | 无 DB 连接信息无法部署任何环境 |
| P0 | [§3.6 Nginx vhost](./README.md) | 无 nginx vhost 草案 ECS 上无法提供 HTTPS |
| P0 | [§3.1 Stack 清单与镜像](./README.md) | 无镜像 / 副本数则 `docker stack deploy` 不可执行 |
| P1 | [§3.5 持久化与文件存储](./README.md) | 无 volume 方案部署后素材上传会丢 |
| P1 | [§3.4 配置与环境变量](./README.md) | 无环境变量清单则仅能启动默认账号 |
| P1 | [§3.7 发布与回滚](./README.md) | 无发布流程无法灰度 |
| P2 | [§3.8 验证](./README.md) | 无验证 checklist 则上线后无法人工复查 |
| P2 | [§3.2 Swarm 网络与复用约束](./README.md) | 网络名不清会导致 NGINX 上游不可达 |

> **验证原则**：所有部署后验证（冒烟用例 / 域名解析 / HTTPS 证书检查 / API 调用）均在 ECS 远程环境执行，**禁止本地验证**（参见用户偏好记忆 `部署验证执行环境偏好`）。

---

## 7. 素材预览依赖（PPT 转 PDF + PDF.js 静态资源）

> 对应规格 v1.2：素材详情页提供 PDF / PPT / MP4 三种行内浏览样式。PPT 依赖后端 LibreOffice 转 PDF（→ `material.preview_pdf_path`），PDF / PPT 共同依赖前端 PDF.js (`pdfjs-dist ^4.7.76`)。

### 7.1 PPT 转 PDF：LibreOffice 系统依赖

- **后端镜像**（[backend/Dockerfile](../../backend/Dockerfile)）在 `apt-get install` 段已加入 `libreoffice-core libreoffice-impress`（仅核心 + Impress 包，避免 writer / calc 冗余）：
  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends \
          libreoffice-core \
          libreoffice-impress \
          fonts-noto-cjk \
      && rm -rf /var/lib/apt/lists/*
  ```
  预计额外镜像体积约 +200MB（Debian slim + 清华镜像源）。
- **后端配置**（[backend/.env.example](../../backend/.env.example)）：
  ```env
  # LibreOffice headless 调用路径（容器内默认 /usr/bin/libreoffice）
  LIBREOFFICE_PATH=/usr/bin/libreoffice
  # PPT → PDF 单文件超时（秒），超时后仅记 logger，不阻塞上传
  PPT_CONVERT_TIMEOUT=60
  ```
- **本地开发**：
  - macOS：`brew install --cask libreoffice`
  - Windows：`choco install libreoffice`
  - 验证：`libreoffice --version` 必须 ≥ 7.0；`which libreoffice`（macOS/Linux）输出可执行文件路径。
- **行为兜底**：转换失败 / 超时 / LibreOffice 未安装时仅写 logger；上传不阻塞；`material.preview_pdf_path` 保持为 NULL。详情页与 `/api/public/materials/{id}/stream` 对 NULL 情况自动降级为"下载到本地"，用户体验不破。

### 7.2 PDF.js 静态资源：`pdf.worker.min.mjs`

- 前端构建期：[frontend/vite.config.ts](../../frontend/vite.config.ts) + [frontend/package.json](../../frontend/package.json) 安装 `pdfjs-dist ^4.7.76`，构建后 `pdf.worker.min.mjs` 复制到 `frontend/dist/pdf.worker.min.mjs`。
- **镜像验证**：
  ```bash
  # 容器内检查
  docker stack exec learning-hub-app ls -la /usr/share/nginx/html/pdf.worker.min.mjs
  # 预期：文件存在，体积约 1MB

  # 远程验证
  curl -I https://learning-hub.smartmoves.com.cn/pdf.worker.min.mjs
  # 预期：HTTP/2 200 + content-type: application/javascript
  ```
- **nginx-gateway 适配**（`nginx-gateway` Stack 的 `learning-hub` vhost 内追加）：
  ```nginx
  location = /pdf.worker.min.mjs {
      proxy_pass http://learning-hub-app/static/pdf.worker.min.mjs;
      proxy_set_header Host $host;
      add_header Cache-Control "public, max-age=31536000, immutable";
      add_header Content-Type "application/javascript";
  }
  ```
  若 nginx-gateway 静态目录已挂载 `learning-hub-app` 容器内 `/usr/share/nginx/html/`，则该文件可被直接服务，无需反代。
- **本地开发**：启动 `cd frontend && npm run dev` 后 Vite 已内置 static file serving，访问 `http://localhost:5173/pdf.worker.min.mjs` 验证。

### 7.3 验证 checklist（§3.8 联动）

ECS 远程验证阶段追加：

- [ ] 容器内 `which libreoffice` 非空，`libreoffice --version` 正常输出
- [ ] 容器内 `ls /usr/share/nginx/html/pdf.worker.min.mjs` 存在
- [ ] 后端 `GET /api/public/materials/{ppt_id}/stream` 响应头 `Content-Type: application/pdf` + `Content-Disposition: inline`
- [ ] 前端 `https://learning-hub.smartmoves.com.cn/?view=viewer&id=<ppt_id>&cw=<courseware_id>` 加载 P-VIEWER-PPT 并能翻页

---

## 8. 课件内素材顺序编辑（v1.5）部署注意事项

> 对应规格 v1.5：管理员可在课件表单内通过拖拽调整素材顺序，前台按该顺序展示。本节为 v1.5 发布的部署要点与回滚预案。

### 8.1 数据库迁移（必须）

- v1.5 引入新迁移 `d2e3f4a5b6c7_add_courseware_material_sort_order`（`backend/alembic/versions/2026_07_10_1800-d2e3f4a5b6c7_add_courseware_material_sort_order.py`）。
- 后端容器启动时 `entrypoint.sh` 自动 `alembic upgrade head`（见 [backend/entrypoint.sh](../../backend/entrypoint.sh)），新版本首次启动即应用迁移并回填既有课件的 `sort_order`。
- 迁移内容（PostgreSQL）：
  1. `ALTER TABLE courseware_material ADD COLUMN sort_order INTEGER`（nullable=True）
  2. 回填：`UPDATE ... SET sort_order = sub.rn - 1 FROM (SELECT courseware_id, material_id, ROW_NUMBER() OVER (PARTITION BY courseware_id ORDER BY material_id) AS rn FROM courseware_material) sub WHERE ...`（按 material_id 升序回填 0..N-1）
  3. `ALTER TABLE courseware_material ALTER COLUMN sort_order SET NOT NULL DEFAULT 0`
  4. `CREATE INDEX ix_courseware_material_courseware_order ON courseware_material (courseware_id, sort_order)`
- 旧镜像如果仍然连接已升级的 DB，会因代码侧 schema 期待 `sort_order` 而抛 500；务必先升镜像再迁数据（实际 entrypoint.sh 同进程内串行执行，发布脚本同步替换两镜像即满足此约束）。

### 8.2 前端依赖

- v1.5 新增依赖 `@dnd-kit/core ^6.3.1` / `@dnd-kit/sortable ^8.0.0` / `@dnd-kit/utilities ^3.2.2`（[frontend/package.json](../../frontend/package.json)）。
- 本地构建前需 `npm ci` 同步 lockfile；CI 发布镜像时 publish.ps1 已带 `npm ci` 步骤。
- 验证：构建后 `frontend/dist` 体积约 +50KB（gzip 约 +20KB）；不引入额外系统级依赖。

### 8.3 部署顺序

1. 确认 `git` 主干已包含本节对应的代码与迁移文件。
2. 本地 `pytest tests/test_courseware_material_order.py` 全绿（AC-041~050）。
3. 本地 `cd frontend && npm ci && npm run typecheck && npm run build` 无 TS / 构建错误。
4. ECS 上使用 `deploy/ecs/publish.ps1 -SkipNginx` 推送新镜像；publish.ps1 已包含 `alembic upgrade head`。
5. 验证迁移已应用：
   ```bash
   docker exec $(docker ps -q -f name=learning-hub_backend.1 | head -1) alembic current
   # 期望输出包含 d2e3f4a5b6c7 (head)
   ```
6. 验证新端点已被加载（不鉴权应 401）：
   ```bash
   curl -i -X PUT https://learning-hub.smartmoves.com.cn/api/admin/coursewares/1/materials/order \
     -H "Content-Type: application/json" \
     -d '{"materialIds":[1]}'
   # 期望：HTTP/1.1 401 (admin_principal 拦截)，不是 404
   ```

### 8.4 回滚预案

- **完整回滚**（推荐，v1.5 涉及 schema 变更）：
  ```bash
  # SSH 到 ECS:
  docker -H ssh://root@121.199.53.233 stack rm learning-hub
  # 本地回退 IMAGE_TAG 后重新 publish：
  cd D:\szp\work\learning-hub\deploy\ecs
  .\publish.ps1 -SkipBuild -SkipNginx
  ```
- **仅数据库回滚**（应急止血，代码侧仍可能 500）：
  ```bash
  docker exec $(docker ps -q -f name=learning-hub_backend.1 | head -1) alembic downgrade -1
  # 此时镜像仍为 v1.5：API 响应中 sortOrder 字段仍会返回，但 courseware_material.sort_order 列已不存在，
  # 会抛 500。仅作为"前端不动、应用层先关排序功能"的应急处理。正式修复需重发旧版。
  ```
- **仅前端回滚**（保留后端 v1.5）：
  ```bash
  docker service update --image lh-frontend:<prev-tag> learning-hub_frontend
  # 前端 v1.4 不识别 sortOrder 字段，但会忽略额外字段；功能降级为"无拖拽排序"。
  ```

---

## 9. 修订记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.3 | 2026-07-10 | 新增 §8 课件内素材顺序编辑（v1.5）部署注意事项：迁移说明（d2e3f4a5b6c7）/ 前端依赖 / 部署顺序 / 完整回滚 + 仅 DB / 仅前端回滚预案 |
| v0.2 | 2026-07-07 | 新增 §7 素材预览依赖：LibreOffice 容器安装 + .env.example 配置 + 本地 brew/choco 安装路径 + `pdf.worker.min.mjs` nginx 静态资源 + 验证 checklist |
| v0.1 | 2026-07-06 | 骨架版：记录 ECS / Swarm / Stack 名 / 域名 / 复用资源等关键信息；后续章节待补充 |
