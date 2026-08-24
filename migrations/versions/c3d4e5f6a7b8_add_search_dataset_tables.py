"""Add search dataset tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-24 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_datasets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("total_keywords", sa.Integer(), nullable=False),
        sa.Column("total_observations", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "search_keywords",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("search_intent", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["search_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_keywords_dataset_id", "search_keywords", ["dataset_id"])
    op.create_index(
        "ix_search_keywords_normalized_keyword", "search_keywords", ["normalized_keyword"]
    )
    op.create_table(
        "search_ranking_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("search_engine", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("device", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["search_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_ranking_observations_dataset_id",
        "search_ranking_observations",
        ["dataset_id"],
    )
    op.create_index(
        "ix_search_ranking_observations_keyword",
        "search_ranking_observations",
        ["keyword"],
    )
    op.create_index(
        "ix_search_obs_identity",
        "search_ranking_observations",
        ["keyword", "target_url", "device", "observed_at"],
    )
    op.create_table(
        "search_competitor_rankings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("competitor_domain", sa.String(length=255), nullable=False),
        sa.Column("competitor_url", sa.String(length=2048), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["search_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_competitor_rankings_dataset_id",
        "search_competitor_rankings",
        ["dataset_id"],
    )
    op.create_index(
        "ix_search_competitor_rankings_keyword",
        "search_competitor_rankings",
        ["keyword"],
    )


def downgrade() -> None:
    op.drop_table("search_competitor_rankings")
    op.drop_table("search_ranking_observations")
    op.drop_table("search_keywords")
    op.drop_table("search_datasets")
