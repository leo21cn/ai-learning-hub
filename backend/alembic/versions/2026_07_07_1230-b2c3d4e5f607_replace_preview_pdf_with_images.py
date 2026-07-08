"""replace material.preview_pdf_path with preview_images_dir

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e5f6
Create Date: 2026-07-07 12:30:00.000000

变更动机:
- 原方案把 PPT 转成 PDF,前端用 PDF.js 单页渲染;
- 新方案把 PPT 每页拆成 PNG 图片,前端直接 <img> 显示,
  减少 PDF.js 依赖、加载更快、移动端更省内存。

迁移策略:
- 新增列 preview_images_dir(可空字符串)
- 旧列 preview_pdf_path 保留(不删除),用于版本兼容;新代码不再读/写它
  (删除列属于破坏性变更,且无业务方依赖,谨慎起见保留)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f607"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material",
        sa.Column("preview_images_dir", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("material", "preview_images_dir")
