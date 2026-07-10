"""add access session

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f607
Create Date: 2026-07-10 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b2c3d4e5f607"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_session",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("courseware_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "client_leave",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("ua", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_access_session_duration_nonneg",
        ),
        sa.ForeignKeyConstraint(
            ["courseware_id"],
            ["courseware.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["material.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["access_token.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="访问会话;记录 token + 课件 + 素材 + 起止时间 + 停留秒数",
    )
    op.create_index(
        "ix_access_session_token_started",
        "access_session",
        ["token_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_access_session_token_material",
        "access_session",
        ["token_id", "material_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_access_session_token_courseware",
        "access_session",
        ["token_id", "courseware_id", "started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_session_courseware_id"),
        "access_session",
        ["courseware_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_session_material_id"),
        "access_session",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_session_token_id"),
        "access_session",
        ["token_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_access_session_token_id"), table_name="access_session"
    )
    op.drop_index(
        op.f("ix_access_session_material_id"), table_name="access_session"
    )
    op.drop_index(
        op.f("ix_access_session_courseware_id"), table_name="access_session"
    )
    op.drop_index(
        "ix_access_session_token_courseware", table_name="access_session"
    )
    op.drop_index(
        "ix_access_session_token_material", table_name="access_session"
    )
    op.drop_index(
        "ix_access_session_token_started", table_name="access_session"
    )
    op.drop_table("access_session")
