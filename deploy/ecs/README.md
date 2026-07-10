# Learning Hub ECS 发布

将 Learning Hub 以 Docker Swarm Stack 形式发布到阿里云 ECS `121.199.53.233`,
复用同集群内已有的 `postgres` Stack(数据库)和 `nginx-gateway` Stack(HTTPS 终止 + 反代)。

> 适用 Stack: `learning-hub`
> 部署形态: Swarm Stack(backend + frontend 两个 service)
> HTTPS: 由 `nginx-gateway` 终止,本脚本自动申请 acme.sh 证书并追加 vhost

> **v1.5 变更**:新增 `courseware_material.sort_order` 列(迁移 `d2e3f4a5b6c7`)、专用素材顺序接口、dnd-kit 前端依赖。详见 [§5a 验收清单](#5a-v15-验收清单) 与 `doc/deploy/README.md §8 部署注意事项`。

---

## 1. 一次性的 ECS 准备

确认 ECS 上已存在(本脚本不创建):
- Swarm 集群已 `docker swarm init` 完毕(`docker info | grep "Swarm: active"` 为 `active`)
- Stack `postgres`(服务名 `postgres_postgres`,位于网络 `agent-mcp-container_agent-mcp-net`)
- Stack `nginx-gateway`(服务名 `nginx-gateway_nginx`,位于网络 `docker_default`)
- 公网域名 `learning-hub.smartmoves.com.cn` 已解析到 `121.199.53.233`

> 这三个依赖是本机 `publish.ps1` 的前置。任一缺失都会让发布在最后两步失败。

本机要求:
- PowerShell 5.1+ / Docker / scp / ssh 均在 PATH 中
- 本机 `~/.ssh/id_ed25519` 公钥已加入 ECS `root@121.199.53.233` 的 `~/.ssh/authorized_keys`

## 2. 首次发布

```powershell
cd D:\szp\work\learning-hub\deploy\ecs
cp .env.example .env
# 编辑 .env,填真实值(尤其是 DATABASE_PASSWORD / JWT_SECRET / DASHSCOPE_API_KEY)

.\publish.ps1
```

## 3. `.env` 字段说明

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `ECS_SSH_USER` / `ECS_HOST` / `ECS_SSH_KEY_PATH` | SSH 登录凭据 | `root` / `121.199.53.233` / `~/.ssh/id_ed25519` |
| `ECS_REMOTE_DIR` | ECS 工作目录 | `/root/learning-hub` |
| `IMAGE_TAG` | 本机构建的两镜像共享 tag | `2026-07-08` |
| `POSTGRES_NETWORK_NAME` | postgres 服务所在 overlay 网络 | `agent-mcp-container_agent-mcp-net` |
| `POSTGRES_SERVICE_NAME` | stack DNS 服务名 | `postgres_postgres` |
| `NGINX_NETWORK_NAME` | nginx-gateway 服务所在 overlay 网络 | `docker_default` |
| `DATABASE_USER` / `DATABASE_PASSWORD` | 复用 postgres stack 现有账号 | `agent_mcp` / (取自 `.env`) |
| `DATABASE_NAME` | 本服务独立数据库名 | `learning_hub` |
| `ADMIN_TOKEN` | 后台登录 token | `shleeyuan` |
| `JWT_SECRET` | JWT 签名密钥,32+ 字符 | `openssl rand -hex 32` |
| `DASHSCOPE_API_KEY` | 阿里云百炼 qwen-plus key(留空降级) | `sk-...` |
| `LH_DOMAIN` | 公网域名(acme.sh 申请证书用) | `learning-hub.smartmoves.com.cn` |

## 4. 常用参数

```powershell
# 跳过本机构建(镜像已存在于本机时)
.\publish.ps1 -SkipBuild

# 跳过 nginx-gateway 配置变更(仅重发应用)
.\publish.ps1 -SkipNginx

# 调长等待 timeout
.\publish.ps1 -WaitHealthyTimeout 600
```

## 5. 验收清单(脚本成功后逐项核对)

```bash
# SSH 到 ECS 后:
docker stack ps learning-hub                          # backend / frontend 均 Running
curl -I https://learning-hub.smartmoves.com.cn/        # HTTP/2 200
curl -I http://learning-hub.smartmoves.com.cn/         # 301 → https://
curl https://learning-hub.smartmoves.com.cn/api/public/health   # {"status":"UP"}

# 进入 backend 容器看 alembic 是否已 upgrade head:
docker exec $(docker ps -q -f name=learning-hub_backend.1 | head -1) alembic current
# 期望输出包含 d2e3f4a5b6c7 (head)，且 head 位置

# 验证新端点路由已被加载(不鉴权应 401，不是 404):
curl -i -X PUT https://learning-hub.smartmoves.com.cn/api/admin/coursewares/1/materials/order \
  -H "Content-Type: application/json" \
  -d '{"materialIds":[1]}'
# 期望: HTTP/1.1 401 (admin_principal 拦截)

# 验证课程表单 UI 有拖拽排序器
curl -s https://learning-hub.smartmoves.com.cn/ | grep -E 'cw-material-sorter' || echo "前端尚未构建"

# 看 nginx-gateway 是否已 reload:
docker exec nginx-gateway_nginx nginx -T 2>&1 | grep learning-hub

# 看证书自动续期 cron:
docker exec nginx-gateway_nginx crontab -l | grep acme
```

## 6. 文件清单

| 文件 | 作用 |
| --- | --- |
| `README.md` | 本文档 |
| `.env.example` | 环境变量模板(复制为 .env 后填实际值) |
| `.gitignore` | 忽略 .env / *.tar / *.log |
| `compose.yml` | Swarm Stack 编排(backend + frontend 两 service,接两个 external 网络) |
| `publish.ps1` | 主发布脚本(本机执行,串联 build / save / scp / 远端 deploy) |
| `remote-setup.sh` | 在 ECS 上创建 `lh_storage` named volume + 工作目录 |
| `db-init.sh` | 在 postgres stack 上幂等创建 `learning_hub` 数据库 |
| `nginx-vhost-apply.sh` | 在 nginx-gateway 上申请/复用证书 + 追加 vhost + reload |
| `nginx-vhost.snippet` | vhost 主体(80 redirect + 443 ssl + upstream) |

## 7. 回滚

```bash
# 仅移除 stack(保留 volume / 网络 / nginx 配置):
docker stack rm learning-hub

# 同时删除数据卷(慎用,会清除所有上传素材):
docker stack rm learning-hub
docker volume rm lh_storage

# 撤销 nginx-gateway 上追加的 vhost:
# 找到备份 cp -a 生成的 nginx.conf.bak.YYYYMMDDHHMMSS,反向覆盖:
# /root/nginx-smartmoves/nginx.conf.bak.20260708120000 /root/nginx-smartmoves/nginx.conf
# 然后 docker exec nginx-gateway_nginx nginx -s reload
```

## 8. 故障排查

| 现象 | 排查 |
| --- | --- |
| `unable to prepare context` | docker build 时工作目录含 `.dockerignore` 或路径问题;脚本默认 `backend/`、`frontend/` 目录 |
| SSH 失败 | 检查 `~/.ssh/id_ed25519` 权限(`chmod 600`)、ECS `authorized_keys` 是否含本机公钥 |
| `docker stack deploy` 网络错误 | 确认 `POSTGRES_NETWORK_NAME` / `NGINX_NETWORK_NAME` 是 `docker network ls` 里真实存在的 overlay 网络 |
| backend 反复 Restarting | 多半是连不上数据库:`docker service logs learning-hub_backend` 看 alembic upgrade 是否因密码/库名错失败 |
| acme.sh 申请证书失败 | 看 `nginx-vhost-apply.sh` 输出:可能是 80 端口未对公网暴露(需要 nginx-gateway 监听 80 + 转发到 acme-challenge 路径)或 DNS 未生效(`dig +short learning-hub.smartmoves.com.cn` 应返回 ECS IP) |
| `nginx -t` 失败 | 检查 `nginx-vhost.snippet` 插入位置;可手动从 `nginx.conf.bak.YYYYMMDDHHMMSS` 恢复 |
| 镜像 tar 巨大传输慢 | backend 含 LibreOffice + 中文字体约 400MB,首次 5-10 分钟属正常;后续通过 layer cache 加速 |

## 9. 后续可改进(不在本版范围)

- 把 learning-hub 切到独立 PG user(目前与 agent-mcp 共享 `agent_mcp` 账号)
- 镜像推到阿里云 ACR(目前 save/load 单机传输)
- 多副本 + 滚动更新
- nginx-gateway 主配置改造成 `include conf.d/*.conf` 模式(目前是单文件,需要 `awk` 精准插入)
- 监控告警(Prometheus + Loki + Sentry)
- 备份与 PITR

## 10. 关键事实快照(2026-07-08 实地调查)

- `postgres stack` 现状:`postgres_postgres` 服务(postgres:15-alpine)已被 `agent-mcp-container` 复用,DB=`agent_mcp_billing`、User=`agent_mcp`、Pwd=`REMOVED-SECRET-PASSWORD`
- `nginx-gateway stack` 现状:`nginx-gateway_nginx`(nginx:1.25-alpine)监听 80 + 443,主配置 `/root/nginx-smartmoves/nginx.conf` 直接 bind mount 到容器内 `/etc/nginx/nginx.conf`(单文件,非 conf.d include 模式)
- 跨 stack 通信:`docker_default` 是 swarm 默认网络,nginx-gateway / real-time-talk 都在上面;postgres 单独在 `agent-mcp-container_agent-mcp-net`
