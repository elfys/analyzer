"""require instrument_id for iv conditions

Revision ID: 48fa2a586f99
Revises: fdf656f33b09
Create Date: 2023-03-06 11:15:11.846343

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "48fa2a586f99"
down_revision = "87540ed003e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "iv_conditions", "instrument_id", existing_type=mysql.SMALLINT(), nullable=False
    )


def downgrade() -> None:
    op.alter_column("iv_conditions", "instrument_id", existing_type=mysql.SMALLINT(), nullable=True)
