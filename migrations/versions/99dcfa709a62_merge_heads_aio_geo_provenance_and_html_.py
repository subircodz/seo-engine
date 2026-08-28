"""merge heads: aio_geo_provenance and html_content_column

Revision ID: 99dcfa709a62
Revises: 20260828_aio_geo_provenance, 5e4c59abfe15
Create Date: 2026-08-28 19:28:56.397182

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '99dcfa709a62'
down_revision: tuple[str, None] = ('20260828_aio_geo_provenance', '5e4c59abfe15')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
