"""initial crawl tables

Revision ID: 0001
Revises:
Create Date: 2026-08-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
    )
    op.create_index("ix_crawl_runs_status", "crawl_runs", ["status"])

    op.create_table(
        "crawl_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(32),
            sa.ForeignKey("crawl_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("html_size", sa.Integer(), nullable=True),
    )
    op.create_index("ix_crawl_pages_run_id", "crawl_pages", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_crawl_pages_run_id", "crawl_pages")
    op.drop_table("crawl_pages")
    op.drop_index("ix_crawl_runs_status", "crawl_runs")
    op.drop_table("crawl_runs")
