"""add material preview_pdf_path

Revision ID: a1b2c3d4e5f6
Revises: 11f9c69846a9
Create Date: 2026-07-07 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "11f9c69846a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为素材表新增 preview_pdf_path 字段：PPT 上传后由 LibreOffice 转换为 PDF 的存储路径
    op.add_column(
        "material",
        sa.Column("preview_pdf_path", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("material", "preview_pdf_path")