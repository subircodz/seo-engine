"""Add diagnosis results table

Revision ID: a1b2c3d4e5f6
Revises: 741e30c9a8f0
Create Date: 2026-08-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "741e30c9a8f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnosis_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("total_issues", sa.Integer(), nullable=False),
        sa.Column("issues_by_priority", sa.JSON(), nullable=False),
        sa.Column("issues_by_severity", sa.JSON(), nullable=False),
        sa.Column("issues_by_category", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("top_affected_pages", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("diagnosis_results", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_diagnosis_results_run_id"), ["run_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("diagnosis_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_diagnosis_results_run_id"))
    op.drop_table("diagnosis_results")
