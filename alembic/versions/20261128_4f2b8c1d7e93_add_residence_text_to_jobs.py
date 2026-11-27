"""add residence_text to jobs

Revision ID: 4f2b8c1d7e93
Revises: 9c4e1a7b2d60
Create Date: 2026-11-28 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f2b8c1d7e93"
down_revision: str | Sequence[str] | None = "9c4e1a7b2d60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows get "": the next search that sees them again fills in the real value.
    op.add_column(
        "jobs", sa.Column("residence_text", sa.String(), server_default="", nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("jobs", "residence_text")
