"""Add performance, entity, and optimization tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create performance_findings table
    op.create_table(
        "performance_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("search_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("description", sa.String(2048), nullable=False, server_default=""),
        sa.Column(
            "recommendation", sa.String(2048), nullable=False, server_default=""
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_perf_findings_dataset_id", "performance_findings", ["dataset_id"]
    )
    op.create_index(
        "ix_perf_findings_dataset_url",
        "performance_findings",
        ["dataset_id", "url"],
    )

    # Create entity_signals table
    op.create_table(
        "entity_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("search_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(512), nullable=False, server_default=""),
        sa.Column("entity_text", sa.String(512), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("domain", sa.String(255), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_entity_signals_dataset_id", "entity_signals", ["dataset_id"])
    op.create_index("ix_entity_signals_keyword", "entity_signals", ["keyword"])
    op.create_index(
        "ix_entity_signals_dataset_keyword",
        "entity_signals",
        ["dataset_id", "keyword"],
    )

    # Create optimization_recommendations table
    op.create_table(
        "optimization_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("search_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.String(4096), nullable=False),
        sa.Column("impact", sa.String(16), nullable=False),
        sa.Column("effort", sa.String(16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("affected_keywords", sa.JSON(), nullable=True),
        sa.Column("affected_urls", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column(
            "source_engine", sa.String(64), nullable=False, server_default=""
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_opt_recs_dataset_id",
        "optimization_recommendations",
        ["dataset_id"],
    )
    op.create_index(
        "ix_opt_recs_dataset_category",
        "optimization_recommendations",
        ["dataset_id", "category"],
    )


def downgrade() -> None:
    op.drop_table("optimization_recommendations")
    op.drop_table("entity_signals")
    op.drop_table("performance_findings")
