"""Add industry intelligence table

Revision ID: 123456789abc
Revises: f6a7b8c9d0e1
Create Date: 2026-08-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "123456789abc"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create industry intelligence table."""
    op.create_table(
        "industry_intelligence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "dataset_id",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("profile", sa.String(length=64), nullable=False),
        sa.Column("total_keywords", sa.Integer(), nullable=False),
        sa.Column("visibility_score", sa.Float(), nullable=False),
        sa.Column("aio_visibility", sa.Float(), nullable=False),
        sa.Column("geo_visibility", sa.Float(), nullable=False),
        sa.Column("cannibalization_issues", sa.Integer(), nullable=False),
        sa.Column("volatility_score", sa.Float(), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("opportunities", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["search_datasets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id"),
    )
    op.create_index(
        "ix_industry_intelligence_dataset_id",
        "industry_intelligence",
        ["dataset_id"],
    )


def downgrade() -> None:
    """Drop industry intelligence table."""
    op.drop_index("ix_industry_intelligence_dataset_id", table_name="industry_intelligence")
    op.drop_table("industry_intelligence")
