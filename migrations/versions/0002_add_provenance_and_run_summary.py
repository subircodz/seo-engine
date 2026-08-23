"""Add crawl provenance and run summary columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("crawl_runs") as batch:
        batch.add_column(sa.Column("total_pages", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("crawl_pages") as batch:
        batch.add_column(sa.Column("content_type", sa.Text(), nullable=True))
        batch.add_column(sa.Column("depth", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("parent_url", sa.Text(), nullable=True))

    op.create_index("ix_crawl_pages_url", "crawl_pages", ["url"])


def downgrade() -> None:
    op.drop_index("ix_crawl_pages_url", table_name="crawl_pages")

    with op.batch_alter_table("crawl_pages") as batch:
        batch.drop_column("parent_url")
        batch.drop_column("depth")
        batch.drop_column("content_type")

    with op.batch_alter_table("crawl_runs") as batch:
        batch.drop_column("error_count")
        batch.drop_column("total_pages")
