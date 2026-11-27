"""add chars_read to job_extractions

Revision ID: 5033f70915ad
Revises: 3737379952b4
Create Date: 2026-11-25 21:24:42.706731

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5033f70915ad"
down_revision: str | Sequence[str] | None = "3737379952b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job_extractions", sa.Column("chars_read", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job_extractions", "chars_read")
