"""Add explicit provenance fields to AIO/GEO observations.

Revision ID: 20260828_aio_geo_provenance
Revises: 20260828_jobs
"""

import sqlalchemy as sa
from alembic import op

revision = "20260828_aio_geo_provenance"
down_revision = "20260828_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("aio_observations", "geo_observations"):
        op.add_column(
            table,
            sa.Column(
                "observation_kind", sa.String(length=32), nullable=False, server_default="manual"
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "provider_name", sa.String(length=128), nullable=False, server_default="unknown"
            ),
        )
        op.add_column(table, sa.Column("provider_request_id", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("methodology", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    for table in ("geo_observations", "aio_observations"):
        op.drop_column(table, "methodology")
        op.drop_column(table, "provider_request_id")
        op.drop_column(table, "provider_name")
        op.drop_column(table, "observation_kind")
