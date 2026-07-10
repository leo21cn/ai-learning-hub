"""add courseware_material.sort_order

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-10 18:00:00.000000

变更动机:
- 课件内的素材需要可编辑的展示顺序（学员学习路径）;
- 在 M:N 关联表 courseware_material 上新增 sort_order 字段,
  按 courseware 内 0..N-1 连续编号。

迁移策略:
1. 新增列 sort_order(可空,先回填再收紧)
2. 回填: 按 material_id 升序, 在每个 courseware 内 ROW_NUMBER() 编号 0..N-1
   - PostgreSQL 与 SQLite 均支持窗口函数 row_number() over()
3. 收紧为 NOT NULL(默认 0)
4. 新增复合索引 ix_courseware_material_courseware_order (courseware_id, sort_order)
   加速按课件取有序素材
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 新增列,先允许 NULL,避免回填失败时整张表被锁
    op.add_column(
        "courseware_material",
        sa.Column("sort_order", sa.Integer(), nullable=True),
    )

    # 2) 回填: 按 (courseware_id, material_id) 计算每个 courseware 内的行号
    #    兼容 PostgreSQL 和 SQLite;窗口函数 row_number() 在两者均可用。
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE courseware_material AS cm
                SET sort_order = sub.rn - 1
                FROM (
                    SELECT courseware_id,
                           material_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY courseware_id
                               ORDER BY material_id
                           ) AS rn
                    FROM courseware_material
                ) AS sub
                WHERE cm.courseware_id = sub.courseware_id
                  AND cm.material_id = sub.material_id
                """
            )
        )
    else:
        # SQLite 等价写法
        op.execute(
            sa.text(
                """
                UPDATE courseware_material
                SET sort_order = (
                    SELECT (rn - 1)
                    FROM (
                        SELECT courseware_id AS cid,
                               material_id AS mid,
                               ROW_NUMBER() OVER (
                                   PARTITION BY courseware_id
                                   ORDER BY material_id
                               ) AS rn
                        FROM courseware_material AS cm2
                        WHERE cm2.courseware_id = courseware_material.courseware_id
                    ) sub
                    WHERE sub.cid = courseware_material.courseware_id
                      AND sub.mid = courseware_material.material_id
                )
                """
            )
        )

    # 3) 收紧为 NOT NULL + 默认 0
    op.alter_column(
        "courseware_material",
        "sort_order",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )

    # 4) 复合索引,加速按课件取有序素材
    op.create_index(
        "ix_courseware_material_courseware_order",
        "courseware_material",
        ["courseware_id", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_courseware_material_courseware_order",
        table_name="courseware_material",
    )
    op.alter_column(
        "courseware_material",
        "sort_order",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_column("courseware_material", "sort_order")