"""add u13 u15 o15 age groups

Revision ID: f4a1c2d3e5b6
Revises: c1a7e4b90f22
Create Date: 2026-07-23 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a1c2d3e5b6"
down_revision: str | Sequence[str] | None = "c1a7e4b90f22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add u13/u15/o15 to the agegroup enum.

    Hand-written: autogenerate does not detect new values on an EXISTING enum
    (see CLAUDE.md), so this revision was created without --autogenerate.

    The labels below are the enum MEMBER NAMES ('under_13'), not the values
    ('u13') -- that is what Postgres stores, verified against pg_enum.

    Each value is positioned with AFTER rather than appended, because Postgres
    sorts an enum by definition order. The resulting order matches AgeGroup in
    app/models.py: u7, u8, u9, u10, u11, o11, u12, u13, u14, u15, o14, o15.
    meet_entries.age_group is the only column of this type.
    """
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_13' AFTER 'under_12'")
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'under_15' AFTER 'under_14'")
    op.execute("ALTER TYPE agegroup ADD VALUE IF NOT EXISTS 'over_15' AFTER 'over_14'")


def downgrade() -> None:
    """
    Deliberate no-op. Postgres cannot drop a value from an enum; reversing this
    would mean recreating the type and rewriting every column that uses it,
    which would fail outright if any row had adopted one of the new values.
    An honest no-op beats a clever downgrade that breaks halfway. Same reasoning
    as the a22c63eaf9c0 migration.
    """
