"""Add AIO and GEO observation tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create AIO observations table
    op.create_table(
        "aio_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("search_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(512), nullable=False),
        sa.Column("ai_type", sa.String(32), nullable=False),
        sa.Column("present", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("target_cited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_domain", sa.String(255), nullable=False, server_default=""),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("competitor_cited_domains", sa.JSON(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(128), nullable=False, server_default="manual"),
    )
    op.create_index("ix_aio_obs_dataset_id", "aio_observations", ["dataset_id"])
    op.create_index("ix_aio_obs_keyword", "aio_observations", ["keyword"])
    op.create_index(
        "ix_aio_obs_dataset_keyword",
        "aio_observations",
        ["dataset_id", "keyword"],
    )

    # Create GEO observations table
    op.create_table(
        "geo_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("search_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(512), nullable=False),
        sa.Column("engine_type", sa.String(32), nullable=False),
        sa.Column("target_mentioned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_domain", sa.String(255), nullable=False, server_default=""),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_mentions", sa.JSON(), nullable=True),
        sa.Column("competitor_domains", sa.JSON(), nullable=True),
        sa.Column("citation_urls", sa.JSON(), nullable=True),
        sa.Column("answer_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(128), nullable=False, server_default="manual"),
    )
    op.create_index("ix_geo_obs_dataset_id", "geo_observations", ["dataset_id"])
    op.create_index("ix_geo_obs_keyword", "geo_observations", ["keyword"])
    op.create_index(
        "ix_geo_obs_dataset_keyword",
        "geo_observations",
        ["dataset_id", "keyword"],
    )


def downgrade() -> None:
    op.drop_table("geo_observations")
    op.drop_table("aio_observations")
