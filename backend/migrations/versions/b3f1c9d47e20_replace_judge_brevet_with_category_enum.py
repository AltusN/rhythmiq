"""Replace judges.brevet free text with a judgecategory enum

The column held free text, which drifted across three notations in practice
("Cat I", "level 3", "1"). FIG defines exactly four categories -- General Judges'
Rules 2025-2028 art. 2.6, reproduced in the RG Specific Judges' Rules art. 2.5
(both under spec/) -- so the column becomes an enum and the field is renamed from
`brevet` to `category` to match FIG's own terminology: a judge holds a *brevet*
(the licence) and is awarded a *category* (the grade within it).

Existing values are mapped on a best-effort basis rather than dropped. Anything
unrecognised becomes NULL, which is a meaningful value here: the FIG scale only
covers brevet holders, and nationally-graded judges have no FIG category.

Revision ID: b3f1c9d47e20
Revises: a22c63eaf9c0
Create Date: 2026-07-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f1c9d47e20"
down_revision: str | Sequence[str] | None = "a22c63eaf9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("category_1", "category_2", "category_3", "category_4")

# Best-effort mapping of the free-text values seen in practice. Arabic and roman
# numerals both appear (FIG itself writes only arabic), as does the "level N"
# spelling, so all three are accepted case-insensitively.
BACKFILL = """
    UPDATE judges SET category = CASE
        WHEN lower(btrim(brevet)) IN ('1', 'i', 'cat 1', 'cat i', 'cat. 1', 'cat. i',
                                      'category 1', 'category i', 'level 1')
            THEN 'category_1'::judgecategory
        WHEN lower(btrim(brevet)) IN ('2', 'ii', 'cat 2', 'cat ii', 'cat. 2', 'cat. ii',
                                      'category 2', 'category ii', 'level 2')
            THEN 'category_2'::judgecategory
        WHEN lower(btrim(brevet)) IN ('3', 'iii', 'cat 3', 'cat iii', 'cat. 3', 'cat. iii',
                                      'category 3', 'category iii', 'level 3')
            THEN 'category_3'::judgecategory
        WHEN lower(btrim(brevet)) IN ('4', 'iv', 'cat 4', 'cat iv', 'cat. 4', 'cat. iv',
                                      'category 4', 'category iv', 'level 4')
            THEN 'category_4'::judgecategory
        ELSE NULL
    END
"""

# Reverse direction writes FIG's own notation, so a downgrade+upgrade round trip is
# lossless for anything that mapped cleanly on the way down.
RESTORE = """
    UPDATE judges SET brevet = CASE category
        WHEN 'category_1'::judgecategory THEN 'Category 1'
        WHEN 'category_2'::judgecategory THEN 'Category 2'
        WHEN 'category_3'::judgecategory THEN 'Category 3'
        WHEN 'category_4'::judgecategory THEN 'Category 4'
        ELSE NULL
    END
"""


def upgrade() -> None:
    # The type must be created explicitly: SQLAlchemy only emits CREATE TYPE as part
    # of Table.create(), so add_column alone would fail with "type does not exist".
    judgecategory = sa.Enum(*CATEGORIES, name="judgecategory")
    judgecategory.create(op.get_bind(), checkfirst=True)

    op.add_column("judges", sa.Column("category", judgecategory, nullable=True))
    op.execute(BACKFILL)
    op.drop_column("judges", "brevet")


def downgrade() -> None:
    op.add_column("judges", sa.Column("brevet", sa.String(), nullable=True))
    op.execute(RESTORE)
    op.drop_column("judges", "category")
    # Drop the type too, or it is orphaned and a later re-upgrade fails with
    # "type judgecategory already exists".
    sa.Enum(name="judgecategory").drop(op.get_bind(), checkfirst=False)
