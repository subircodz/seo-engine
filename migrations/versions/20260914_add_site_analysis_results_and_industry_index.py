"""Add site analysis persistence and enforce unique industry datasets.

Revision ID: 20260914_site_analysis
Revises: 99dcfa709a62
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260914_site_analysis"
down_revision: str | None = "99dcfa709a62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_analysis_results",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("crawl_run_id", sa.String(length=32), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("technical_score", sa.Float(), nullable=False),
        sa.Column("content_score", sa.Float(), nullable=False),
        sa.Column("ranking_score", sa.Float(), nullable=False),
        sa.Column("architecture_score", sa.Float(), nullable=False),
        sa.Column("aio_score", sa.Float(), nullable=False),
        sa.Column("geo_score", sa.Float(), nullable=False),
        sa.Column("javascript_score", sa.Float(), nullable=False),
        sa.Column("structured_data_score", sa.Float(), nullable=False),
        sa.Column("core_web_vitals_score", sa.Float(), nullable=False),
        sa.Column("semantic_coverage_score", sa.Float(), nullable=False),
        sa.Column("internal_link_equity_score", sa.Float(), nullable=False),
        sa.Column("search_intent_score", sa.Float(), nullable=False),
        sa.Column("serp_features_score", sa.Float(), nullable=False),
        sa.Column("competitor_gaps_score", sa.Float(), nullable=False),
        sa.Column("indexation_score", sa.Float(), nullable=False),
        sa.Column("eeat_score", sa.Float(), nullable=False),
        sa.Column("content_decay_score", sa.Float(), nullable=False),
        sa.Column("entity_kg_score", sa.Float(), nullable=False),
        sa.Column("advanced_competitor_score", sa.Float(), nullable=False),
        sa.Column("hreflang_score", sa.Float(), nullable=False),
        sa.Column("advanced_link_score", sa.Float(), nullable=False),
        sa.Column("predictive_ranking_score", sa.Float(), nullable=False),
        sa.Column("rag_optimization_score", sa.Float(), nullable=False),
        sa.Column("content_quality_adv_score", sa.Float(), nullable=False),
        sa.Column("pagination_faceted_score", sa.Float(), nullable=False),
        sa.Column("amp_score", sa.Float(), nullable=False),
        sa.Column("overall_grade", sa.String(length=2), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("crux_lcp", sa.Float(), nullable=True),
        sa.Column("crux_fid", sa.Float(), nullable=True),
        sa.Column("crux_cls", sa.Float(), nullable=True),
        sa.Column("crux_inp", sa.Float(), nullable=True),
        sa.Column("crux_ttfb", sa.Float(), nullable=True),
        sa.Column("crux_last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["crawl_run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_analysis_results_analyzed_at",
        "site_analysis_results",
        ["analyzed_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_analysis_results_crawl_run_id",
        "site_analysis_results",
        ["crawl_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_analysis_results_domain",
        "site_analysis_results",
        ["domain"],
        unique=False,
    )

    op.drop_index(
        "ix_industry_intelligence_dataset_id",
        table_name="industry_intelligence",
    )
    op.create_index(
        "ix_industry_intelligence_dataset_id",
        "industry_intelligence",
        ["dataset_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_industry_intelligence_dataset_id",
        table_name="industry_intelligence",
    )
    op.create_index(
        "ix_industry_intelligence_dataset_id",
        "industry_intelligence",
        ["dataset_id"],
        unique=False,
    )
    op.drop_index(
        "ix_site_analysis_results_domain",
        table_name="site_analysis_results",
    )
    op.drop_index(
        "ix_site_analysis_results_crawl_run_id",
        table_name="site_analysis_results",
    )
    op.drop_index(
        "ix_site_analysis_results_analyzed_at",
        table_name="site_analysis_results",
    )
    op.drop_table("site_analysis_results")
