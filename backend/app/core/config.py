"""应用配置:从环境变量加载,可被 .env 文件覆盖。"""
from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置主类。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 数据库 =====
    database_host: str = Field(default="postgres")
    database_port: int = Field(default=5432)
    database_user: str = Field(default="lh")
    database_password: str = Field(default="lh")
    database_name: str = Field(default="learning_hub")
    # 整体连接串优先,留空时自动由各个独立字段拼出。
    database_url: str = Field(default="")

    @computed_field  # type: ignore[misc]
    @property
    def effective_database_url(self) -> str:
        """优先返回 DATABASE_URL 环境变量(供临时覆盖/切换数据库用);
        否则从独立字段拼出 postgresql+psycopg2://<user>:<pwd>@<host>:<port>/<db>。"""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    # ===== Admin =====
    admin_token: str = Field(default="shleeyuan")

    # ===== JWT =====
    jwt_secret: str = Field(default="please-change-me-in-production-32chars-min-length-xxxx")
    jwt_algorithm: str = Field(default="HS256")
    jwt_ttl_hours: int = Field(default=8)

    # ===== CORS =====
    cors_allow_origins: str = Field(default="*")

    # ===== 时区 =====
    timezone: str = Field(default="Asia/Shanghai")

    # ===== 存储 =====
    storage_path: str = Field(default="/app/storage/documents")

    # ===== PPT 转图片 =====
    libreoffice_path: str = Field(default="/usr/bin/libreoffice")
    poppler_path: str = Field(default="/usr/bin/pdftoppm")
    ppt_convert_timeout: int = Field(default=60)

    # ===== 限流 / Redis =====
    storage_redis_url: str = Field(default="")

    # ===== LLM(阿里云百炼 qwen-plus 用于 NL2SQL)=====
    # 留空 → LLM 服务禁用,前台搜索自动降级到关键词 ILIKE。
    dashscope_api_key: str = Field(default="")
    llm_search_model: str = Field(default="qwen-plus")
    llm_sql_timeout_seconds: float = Field(default=8.0)
    llm_sql_max_rows: int = Field(default=20)

    # ===== 日志 =====
    log_level: str = Field(default="INFO")

    @property
    def cors_origins_list(self) -> List[str]:
        return [x.strip() for x in self.cors_allow_origins.split(",") if x.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.dashscope_api_key and self.dashscope_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存的全局配置实例。"""
    return Settings()
