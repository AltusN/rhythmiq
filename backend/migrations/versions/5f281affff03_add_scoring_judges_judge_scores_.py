"""add scoring: judges, judge_scores, routine penalty

Revision ID: 5f281affff03
Revises: 13c4f4f7c987
Create Date: 2026-07-08 23:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f281affff03"
down_revision: str | Sequence[str] | None = "13c4f4f7c987"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "judges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=True),
        sa.Column("brevet", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("first_name", "last_name", "country_code", name="uq_judge_identity"),
    )
    op.create_index(op.f("ix_judges_country_code"), "judges", ["country_code"], unique=False)
    op.create_index(op.f("ix_judges_first_name"), "judges", ["first_name"], unique=False)
    op.create_index(op.f("ix_judges_id"), "judges", ["id"], unique=False)
    op.create_index(op.f("ix_judges_last_name"), "judges", ["last_name"], unique=False)
    op.create_table(
        "judge_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("routine_id", sa.Integer(), nullable=False),
        sa.Column("judge_id", sa.Integer(), nullable=False),
        sa.Column(
            "panel", sa.Enum("difficulty", "execution", "artistry", name="panel"), nullable=False
        ),
        sa.Column("value", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.CheckConstraint("value >= 0", name="ck_judge_score_value_non_negative"),
        sa.CheckConstraint("value % 0.05 = 0", name="ck_judge_score_value_increments"),
        sa.CheckConstraint(
            "panel = 'difficulty' OR value <= 10", name="ck_judge_score_panel_value_cap"
        ),
        sa.ForeignKeyConstraint(["judge_id"], ["judges.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routine_id"], ["routines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "routine_id", "judge_id", "panel", name="uq_judge_score_routine_judge_panel"
        ),
    )
    op.create_index(op.f("ix_judge_scores_id"), "judge_scores", ["id"], unique=False)
    op.add_column(
        "routines",
        sa.Column(
            "penalty", sa.Numeric(precision=6, scale=2), server_default="0", nullable=False
        ),
    )
    op.create_check_constraint("ck_routine_penalty_non_negative", "routines", "penalty >= 0")
    op.create_check_constraint(
        "ck_routine_penalty_increments", "routines", "penalty % 0.05 = 0"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_routine_penalty_increments", "routines", type_="check")
    op.drop_constraint("ck_routine_penalty_non_negative", "routines", type_="check")
    op.drop_column("routines", "penalty")
    op.drop_index(op.f("ix_judge_scores_id"), table_name="judge_scores")
    op.drop_table("judge_scores")
    op.drop_index(op.f("ix_judges_last_name"), table_name="judges")
    op.drop_index(op.f("ix_judges_id"), table_name="judges")
    op.drop_index(op.f("ix_judges_first_name"), table_name="judges")
    op.drop_index(op.f("ix_judges_country_code"), table_name="judges")
    op.drop_table("judges")
