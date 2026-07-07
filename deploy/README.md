# Learning Hub 本地部署说明

## 服务清单

| 服务 | 端口 | 镜像 / 来源 |
| ---- | ---- | -------- |
| PostgreSQL 16 | 5432 | `postgres:16-alpine` |
| Backend (FastAPI) | 8000 | 本地 `backend/Dockerfile` |
| Frontend (Nginx) | 5173 (映射容器 80) | 本地 `frontend/Dockerfile` |

## 启动

```bash
# 在 deploy/ 目录
docker compose up -d --build

# 健康检查
curl http://localhost:8000/api/public/health
curl http://localhost:5173/
```

## 数据卷

- `pgdata`:PostgreSQL 数据持久化(销毁容器不丢数据)
- `storage`:后端 `/app/storage` 素材文件持久化

## 验证清单

- [ ] `GET /api/public/health` → 200 `{"code":"ok","data":{"status":"UP",...}}`
- [ ] `GET /` → 返回 Vite SPA HTML
- [ ] 三容器 healthy:`docker compose ps`

## 阶段 2+ 后

需要:

```bash
# 初始化数据库(首次)
docker compose exec backend alembic upgrade head

# 跑测试
docker compose exec backend pytest
```

## 默认凭据

- Admin Token:`demo`(生产请通过环境变量覆盖)
- 数据库:`lh / lh / learning_hub`

---

## 阶段 7 本地部署验证记录(2026-07-06)

> 覆盖 docker-compose 三服务、playwright 依赖、admin 路径、初始密码、smoke 脚本与全量 e2e。
> 验证环境:Windows 11 + Docker Desktop + Docker Compose v2 + PowerShell。

### 7.1 一键启动

```bash
cd deploy
docker compose up -d --build
docker compose ps          # 看到三个容器 healthy
```

预期输出(均 healthy):

```
NAME          STATUS
lh-postgres   Up X (healthy)
lh-backend    Up X (healthy)
lh-frontend   Up X (healthy)
```

### 7.2 初始凭据 / 入口

| 资源 | 地址 / 值 |
| ---- | -------- |
| 前台首页 | http://localhost:5173/ |
| 后台登录 | http://localhost:5173/admin(Admin Token: `demo`) |
| 后端 health | http://localhost:8000/api/public/health |
| PostgreSQL | `lh / lh / learning_hub`(端口 5432) |

### 7.3 全量后端测试

```bash
docker compose exec backend python -m pytest tests/ -v --tb=short
```

预期:`34 passed in <1s`。覆盖 auth / categories / tags / materials / access_tokens / coursewares 全部业务规则。

### 7.4 UI Smoke 测试清单

打开 http://localhost:5173/ 验证下列路径(无须登录即可看到):

| # | URL | 期望 |
| --- | --- | --- |
| 1 | `/` | 主页 hero + 搜索框 + 最新课件列表 |
| 2 | `/?q=Open` | 搜索结果页 + AI 降级中徽标 |
| 3 | `/?view=locked&id=<RESTRICTED_ID>` | 🔒 锁定页 + 令牌输入框 |
| 4 | `/?view=detail&id=<OPEN_ID>` | 详情页(标题/作者/简介/素材) |

后台 `/admin`(输入 `demo`)验证:

| # | URL | 期望 |
| --- | --- | --- |
| 5 | `/admin/coursewares` | 课件列表 + 新建/编辑/删除 |
| 6 | `/admin/access-tokens` | 令牌列表 + 生成/重新生成/删除 |
| 7 | `/admin/categories`、`/admin/tags`、`/admin/materials` | 三个 CRUD 页正常 |

### 7.5 一键 seed 受限课件(可选)

如需手动验证锁定与解锁 UI 完整闭环:

```bash
docker compose cp backend/tests/_seed_locked.sh backend:/tmp/
docker compose exec backend bash /tmp/_seed_locked.sh
```

返回示例:

```
== categories ==
leaf_id=3
== access tokens ==
tok_id=3
== create restricted courseware ==
code: ok id: 8
```

随后:
1. 浏览器打开 `http://localhost:5173/?view=locked&id=8`
2. 在后台 `/admin/access-tokens` 中重新生成 token 3,获得明文(如 `alpvsa8fagikymmx6epw5u0j`)
3. 粘贴明文到解锁表单 → 点解锁 → 自动跳转 `?view=detail&id=8`,显示完整课件信息

### 7.6 Playwright E2E(可选)

如需跑 Playwright E2E(脚本就绪,需自备 Chromium):

```bash
cd frontend
npm install
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright npx playwright install chromium
npx playwright test
```

详见 [frontend/e2e/README.md](../frontend/e2e/README.md)。

### 7.7 已知坑 / 修复

- **frontend 默认 unhealthy**:Dockerfile 内置的 `wget http://localhost/` 因 Alpine 默认 IPv6(`getent hosts localhost` 优先返回 `::1`)而连接被拒,nginx 只监听 IPv4。
  **修复**:在 [docker-compose.yml](docker-compose.yml) 中覆盖 frontend 的 healthcheck,改用 `curl -fsS http://127.0.0.1/` + `curl -fsS http://127.0.0.1/api/public/health`,同时验证 nginx 自身 + 反向代理到后端。
- **Alpine pip / Debian apt 镜像**:在 backend Dockerfile 中固定为清华镜像,避免国际网络抖动。
- **前端 unlock 时序**:若 `POST /unlock` 还没回 Set-Cookie 就跳到 detail,后端 GET 会回 403。流程上保证 unlock 成功后再切换 view 即可(`LockedPage.handleUnlock` 已处理)。

### 7.8 素材预览依赖（v1.2 新增）

> 背景：v1.2 素材在线浏览能力（PDF / PPT / MP4 三种样式）要求后端安装 LibreOffice 转 PPT→PDF，前端打包包含 PDF.js worker。本节记录本地 docker-compose 环境中的验证要点。

#### 7.8.1 LibreOffice 容器化安装

[backend/Dockerfile](../backend/Dockerfile) 中 `apt-get install` 段已加入：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-core \
        libreoffice-impress \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
```

容器重建后验证：

```bash
docker compose exec backend which libreoffice
# 预期：/usr/bin/libreoffice

docker compose exec backend libreoffice --version
# 预期：LibreOffice 7.x (输出非空)
```

环境变量（[backend/.env.example](../backend/.env.example) 中已注释默认值）：

```env
LIBREOFFICE_PATH=/usr/bin/libreoffice
PPT_CONVERT_TIMEOUT=60
```

#### 7.8.2 PDF.js 静态资源

- [frontend/package.json](../frontend/package.json) 已声明 `pdfjs-dist ^4.7.76`；[frontend/vite.config.ts](../frontend/vite.config.ts) 配置 `optimizeDeps.exclude: ['pdfjs-dist']`。
- 构建后 [frontend/dist/pdf.worker.min.mjs](../frontend/dist/pdf.worker.min.mjs) 由 [`frontend/Dockerfile`](../frontend/Dockerfile) 第 11 行 `cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs dist/pdf.worker.min.mjs` 拷贝；本地不走 Docker 时由 [package.json `build` 脚本](../frontend/package.json) 末尾的 `node scripts/copy-pdfjs-worker.mjs` 完成同样动作。
- 验证：

```bash
# 构建产物检查
ls -la frontend/dist/pdf.worker.min.mjs
# 预期：文件存在，体积约 1MB

# 容器化运行时通过 nginx 访问
docker compose exec frontend ls -la /usr/share/nginx/html/pdf.worker.min.mjs
curl -I http://localhost:5173/pdf.worker.min.mjs
# 预期：HTTP/1.1 200 + content-type: application/javascript
```

#### 7.8.3 P-VIEWER 三种样式 smoke

- **VIDEO**：

  ```bash
  # 在 admin 后台上传 mp4 素材
  # 浏览器访问 http://localhost:5173/?view=detail&id=<courseware_id>
  # 点击"在线浏览" → 跳转 P-VIEWER-VIDEO
  # 预期：p-viewer-video 可见 + 右侧信息面板含时长/大小
  ```

- **PDF**：

  ```bash
  # 上传 PDF 素材后访问 P-VIEWER
  # 预期：p-viewer-pdf 可见，滚动到 50% 处右下角 p-viewer-pdf-page-indicator 更新
  # 连续点击 p-viewer-pdf-zoom-in 三次，p-viewer-pdf-zoom-label 从 100% → 125% → 150% → 175%
  ```

- **PPT**：

  ```bash
  # 上传 PPTX 素材后等 LibreOffice 转 PDF（约 5~10s）
  # 访问 P-VIEWER，预期初始 1 / N
  # 点击 p-viewer-ppt-next 变 2 / N；按 ArrowRight 变 3 / N
  # 到达末页点 p-viewer-ppt-next 后按钮 disabled 且文案变 "已是最后一张"
  ```

#### 7.8.4 /api/public/materials/{id}/stream 响应头验证

```bash
# PPT 转 PDF 成功后
curl -I http://localhost:8000/api/public/materials/<ppt_id>/stream
# 预期：
#   HTTP/1.1 200 OK
#   content-type: application/pdf
#   content-disposition: inline; filename="<name>.pdf"

# VIDEO
curl -I http://localhost:8000/api/public/materials/<video_id>/stream
# 预期：
#   content-type: video/mp4
#   content-disposition: inline; filename="<name>.mp4"
```

#### 7.8.5 已知降级路径

| 场景 | 行为 |
| ---- | ---- |
| LibreOffice 未安装 / 转换失败 | `material.preview_pdf_path = NULL`，P-VIEWER 走"下载到本地"链接 |
| 老数据（v1.1 及之前） | 升级后预览页一律降级为下载；运维可手动跑一次性转换脚本（不入仓） |
| `pdf.worker.min.mjs` 404 | 浏览器控制台报 `Setting up fake worker`，P-VIEWER-PDF / P-VIEWER-PPT 渲染失败；需重新构建 frontend 镜像 |
| 转换超时（>60s） | logger 记 `ppt_to_pdf_timeout`，上传 200 OK，前端走下载兜底 |

---
