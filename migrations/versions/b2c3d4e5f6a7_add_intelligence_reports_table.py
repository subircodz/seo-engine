"""Add intelligence reports table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-24 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intelligence_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("intelligence_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("diagnosis_run_id", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=16), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("overall_assessment", sa.String(), nullable=False),
        sa.Column("root_causes", sa.JSON(), nullable=False),
        sa.Column("top_issues", sa.JSON(), nullable=False),
        sa.Column("quick_wins", sa.JSON(), nullable=False),
        sa.Column("action_plan", sa.JSON(), nullable=False),
        sa.Column("raw_response", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("intelligence_reports", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_intelligence_reports_intelligence_id"),
            ["intelligence_id"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_intelligence_reports_run_id"),
            ["run_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("intelligence_reports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_intelligence_reports_run_id"))
        batch_op.drop_index(batch_op.f("ix_intelligence_reports_intelligence_id"))
    op.drop_table("intelligence_reports")
