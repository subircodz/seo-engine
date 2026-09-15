"""Normalize persisted content quality scores to the report contract.

Revision ID: 20260915_content_quality_scale
Revises: 20260914_site_analysis
Create Date: 2026-09-15

ContentMetrics.quality_score is stored on a 0–100 scale, while
ContentQualityReport.avg_quality_score is a normalized 0–1 value used by
site-analysis scoring and report rendering. Older persisted reports were
written directly from the 0–100 metric average.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260915_content_quality_scale"
down_revision: str | None = "20260914_site_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE content_quality_reports "
            "SET avg_quality_score = avg_quality_score / 100.0 "
            "WHERE avg_quality_score > 1"
        )
    )


def downgrade() -> None:
    # Data normalization is intentionally irreversible. Reversing it blindly
    # could also rescale reports created after this migration.
    pass
