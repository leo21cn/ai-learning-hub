---
kind: logging_system
name: Python 标准库 logging 基础日志系统
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/main.py
    - backend/app/core/config.py
    - backend/alembic/env.py
---

本项目在后端 FastAPI 服务中采用 Python 标准库 `logging` 作为唯一日志框架，未引入 structlog、loguru、uvicorn 自定义 logger 等第三方方案。核心特征如下：

1. **初始化位置与格式**：在 `backend/app/main.py` 的 `create_app()` 顶部通过 `logging.basicConfig(level=..., format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s")` 一次性配置根 logger，格式包含时间戳、级别、模块名和消息体；日志级别由 `app.core.config.Settings.log_level`（默认 `INFO`）经环境变量 `.env` 注入。

2. **Logger 命名空间**：各业务模块统一使用 `logger = logging.getLogger(__name__)` 获取子 logger，形成以包路径为层级的命名树（如 `app.services.ppt_to_images`），便于按模块过滤。

3. **日志级别约定**：代码中仅出现 `logger.warning(...)` 与少量 `logger.info(...)`，未见 `debug/error/exception/critical` 调用，说明当前处于“只记录警告与关键信息”的保守阶段；异常通常直接抛出并由上层中间件或 FastAPI 默认处理器处理，未在业务层显式 `logger.exception`。

4. **请求追踪字段**：应用通过 HTTP 中间件 `add_request_id` 将 `X-Request-Id` 注入 `request.state.request_id`，并在响应头回写；但当前日志格式并未把该 ID 拼入输出，属于可改进点。

5. **Alembic 迁移日志**：`alembic/env.py` 通过 `logging.config.fileConfig(config_file_name)` 加载 Alembic 自身的 logging 配置，与主应用 `basicConfig` 相互独立。

6. **前端无后端式日志**：前端 React/Vite 项目未发现集中化的日志框架，浏览器侧调试依赖控制台输出，不属于本仓库的“服务端日志系统”范畴。

开发者应遵循的规则：
- 新增模块如需日志，先在文件头部 `import logging; logger = logging.getLogger(__name__)`，再按需调用 `logger.warning/info`；避免重复 `basicConfig`。
- 敏感信息（密码、token、完整 SQL）不得写入日志；需要关联请求时优先复用已有的 `X-Request-Id` 并在后续升级格式时纳入。
- 若需结构化 JSON 日志或统一 sink（文件/Stdout/ELK），应在 `main.py` 的 `basicConfig` 处扩展 handler，而非在各模块内单独配置。