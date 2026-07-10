---
kind: configuration_system
name: 基于 pydantic-settings 的环境变量配置系统
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/core/config.py
    - backend/app/main.py
    - backend/.env.example
    - backend/.env
    - frontend/.env.example
    - deploy/ecs/.env.example
---

## 1. 采用的系统与工具

- **后端**：使用 `pydantic_settings.BaseSettings` 作为统一配置加载器，通过环境变量 + `.env` 文件注入，配合 `@computed_field` 做派生值（如数据库连接串）。
- **前端**：Vite 构建期通过 `import.meta.env.VITE_*` 读取 `.env` 中的 `VITE_API_BASE`，用于 API 基地址。
- **部署/发布**：ECS Swarm 脚本与 docker-compose 通过 shell 环境变量或 `.env` 文件向容器注入运行时参数。

## 2. 核心文件与包

| 角色 | 路径 |
| --- | --- |
| 配置模型定义 | `backend/app/core/config.py` |
| 全局缓存入口 | `get_settings()`（同上） |
| 应用装配（CORS、日志级别等） | `backend/app/main.py` |
| Alembic 迁移读取配置 | `backend/alembic/env.py` |
| 限流/存储/LLM 等服务层消费 | `app/services/*.py`、`app/db/__init__.py`、`app/middleware/admin_auth.py` |
| 后端开发模板 | `backend/.env.example` |
| 后端本地覆盖 | `backend/.env`（gitignored） |
| 前端构建期配置模板 | `frontend/.env.example` |
| ECS 发布环境模板 | `deploy/ecs/.env.example` |

## 3. 架构与约定

### 3.1 加载顺序与优先级
- `BaseSettings` 默认从进程环境变量读取；
- `model_config.env_file=".env"` 使同目录下的 `.env` 作为补充源；
- 字段上的 `Field(default=...)` 提供本地开发可运行的默认值；
- 对数据库连接，`effective_database_url` 计算字段优先返回 `DATABASE_URL`，否则拼接 `postgresql+psycopg2://...`，实现“整体 URL 覆盖 / 独立字段拼装”双模式。

### 3.2 全局单例
- `get_settings()` 用 `@lru_cache(maxsize=1)` 缓存实例，全进程共享同一份配置，避免重复解析。
- 各模块在导入时即调用 `_settings = get_settings()` 取到只读对象，不再自行构造。

### 3.3 配置分组与命名
- 所有字段名采用 `UPPER_SNAKE_CASE`，对应同名环境变量；
- 按功能域分块注释：数据库、Admin、JWT、CORS、时区、存储、PPT 转换、Redis 限流、LLM、日志；
- 布尔开关型配置通过空字符串判断（如 `dashscope_api_key` 留空即禁用 LLM），并在 `llm_enabled` 属性中集中表达。

### 3.4 前端配置
- Vite 仅暴露以 `VITE_` 前缀的变量，当前仅有 `VITE_API_BASE=/api`，由前端代码通过 `import.meta.env.VITE_API_BASE` 读取，决定 API 代理目标。
- 开发期 `vite.config.ts` 内硬编码 `/api` → `http://127.0.0.1:18765` 反向代理，生产则交由 Nginx 转发。

### 3.5 部署侧配置
- `deploy/ecs/.env.example` 同时包含 SSH 远程认证、镜像 tag、网络名、数据库连接、后端运行参数（与 `config.py` 字段一一对应）、域名等；
- publish 脚本将其 source 进容器环境变量，与后端 `BaseSettings` 自动对齐。

## 4. 开发者应遵循的规则

1. **新增配置项**：在 `backend/app/core/config.py` 的 `Settings` 类中添加字段，给出合理的 `default=`，并同步更新 `backend/.env.example` 与 `deploy/ecs/.env.example`。
2. **敏感信息不入仓**：真实凭据写入 `backend/.env`（已在 gitignore 中忽略），生产通过 ECS `.env` 或编排平台注入。
3. **不要直接拼连接串**：需要数据库 URL 的地方一律使用 `settings.effective_database_url`，以便 `DATABASE_URL` 覆盖生效。
4. **布尔开关用空串判断**：参考 `llm_enabled`，保持“留空即禁用”的零侵入行为。
5. **前端新变量需加 `VITE_` 前缀**：只有带该前缀的变量会被打包进浏览器，且需在 `frontend/.env.example` 中声明。
6. **修改 CORS、时区、日志级别等运行时参数无需改代码**：全部通过环境变量切换，重启服务即可生效。