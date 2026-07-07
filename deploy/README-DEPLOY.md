# Learning Hub 本机 Docker 部署

## 一键发布

在 `d:\szp\work\learning-hub\deploy\` 目录跑：

```powershell
.\deploy-lh-local.ps1
```

## 脚本功能

1. 探测 Docker Desktop daemon（自动通过 named pipe，免开 2375 端口）
2. 停止 `backend` / `frontend` 容器，保留 `postgres` 容器（省掉 alembic 重跑时间）
3. 重建 `backend` 镜像（含本轮新增的 P-VIEWER 素材预览能力）
4. 重建 `frontend` 镜像（含 Viewer 三子组件）
5. 启动三服务
6. 等待所有容器 healthy（最多 3 分钟）
7. 验证 `openapi.json` 是否已注册 `/api/public/materials/{id}/stream` 等新接口
8. 打印最终访问地址

## 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `-ProjectName` | `deploy` | docker compose project 名称 |
| `-ComposeFile` | `docker-compose.yml` | compose 文件 |
| `-WaitHealthyTimeout` | `180` | 等 healthy 的秒数 |

## 失败排查

构建日志在 `%TEMP%\lh-build-backend.log` / `lh-build-frontend.log`。

## 访问地址

- 前台首页：http://localhost:5173/
- 后台登录：http://localhost:5173/admin（token: `demo`）
- 后端 API：http://localhost:8000/api/docs
- PostgreSQL：localhost:5432（lh / lh / learning_hub）

## 手动运维

```powershell
# 看容器
docker -H npipe:////./pipe/docker_engine compose -p deploy ps

# 看后端日志
docker -H npipe:////./pipe/docker_engine compose -p deploy logs -f backend

# 全停
docker -H npipe:////./pipe/docker_engine compose -p deploy down

# 完整清空（含数据卷）—— 慎用
docker -H npipe:////./pipe/docker_engine compose -p deploy down -v
```
