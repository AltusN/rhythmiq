"""add u7 u9 u11 o11 age groups

Revision ID: a22c63eaf9c0
Revises: 604bed2f1eb3
Create Date: 2026-07-20 07:14:02.776511

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a22c63eaf9c0'
down_revision: str | Sequence[str] | None = '604bed2f1eb3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add u7/u9/u11/o11 to the agegroup enum.

    Hand-written: autogenerate does not detect new values on an EXISTING enum
    (see CLAUDE.md), so this revision was created without --autogenerate.

    The labels below are the enum MEMBER NAMES ('under_8'), not the values
    ('u8') -- that is what Postgres stores, verified against pg_enum.

    Each value is positioned with BEFORE/AFTER rather than appended, because
    Postgres sorts an enum by definition order. Appending would give
    '... over_14, under_7, under_9' and make any ORDER BY on this column
    meaningless. The resulting order matches AgeGroup in app/models.py:
    u7, u8, u9, u10, u11, o11, u12, u14, o14.
    """
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_7' BEFORE 'under_8'")
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_9' AFTER 'under_8'")
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_11' AFTER 'under_10'")
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'over_11' AFTER 'under_11'")


def downgrade() -> None:
    """
    Deliberate no-op. Postgres cannot drop a value from an enum; reversing this
    would mean recreating the type and rewriting every column that uses it,
    which would fail outright if any row had adopted one of the new values.
    An honest no-op beats a clever downgrade that breaks halfway.

    Note this differs from the ethnicity migration, which IS reversible -- that
    one created a new type rather than extending an existing one.
    """
