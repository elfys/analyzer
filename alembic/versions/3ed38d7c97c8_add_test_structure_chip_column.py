"""add test_structure chip column

Revision ID: 3ed38d7c97c8
Revises: 02d18a4cafc5
Create Date: 2023-03-29 09:32:54.096712

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "3ed38d7c97c8"
down_revision = "02d18a4cafc5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chip",
        sa.Column(
            "test_structure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        text(
            """
        UPDATE chip c
            SET c.test_structure = TRUE
            WHERE c.id in (SELECT DISTINCT chip_id FROM ts_conditions)
    """
        )
    )


def downgrade() -> None:
    op.drop_column("chip", "test_structure")
