"""本地开发用：一次性初始化 SQLite 表结构（避免 alembic 兼容性问题）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import Base


def main() -> None:
    s = get_settings()
    _url = s.effective_database_url
    print(f"[dev-init] DATABASE_URL={_url}")
    if _url.startswith("sqlite"):
        engine = create_engine(
            _url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(_url)

    # 注册所有模型（显式导入，避免函数内通配符导入的 lint 限制）
    from app.models.access_token import AccessToken  # noqa: F401
    from app.models.association import (  # noqa: F401
        courseware_access_token,
        courseware_material,
        courseware_tag,
    )
    from app.models.category import Category  # noqa: F401
    from app.models.courseware import Courseware  # noqa: F401
    from app.models.material import Material  # noqa: F401
    from app.models.tag import Tag  # noqa: F401

    Base.metadata.create_all(engine)
    print("[dev-init] tables created:", sorted(Base.metadata.tables.keys()))


if __name__ == "__main__":
    main()
