"""add modality to jobs

Revision ID: 9c4e1a7b2d60
Revises: 5033f70915ad
Create Date: 2026-11-27 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4e1a7b2d60"
down_revision: str | Sequence[str] | None = "5033f70915ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows get "unknown": the next search that sees them again fills in the real value.
    op.add_column(
        "jobs", sa.Column("modality", sa.String(), server_default="unknown", nullable=False)
    )
    op.create_check_constraint(
        "modality", "jobs", "modality IN ('remote','hybrid','onsite','unknown')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_jobs_modality"), "jobs", type_="check")  # name already final
    op.drop_column("jobs", "modality")
