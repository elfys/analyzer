"""remove redundant iv data fields

Revision ID: fdf656f33b09
Revises: 87540ed003e1
Create Date: 2023-03-06 10:37:14.963855

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "fdf656f33b09"
down_revision = "48fa2a586f99"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("iv_data__chip", "iv_data", type_="foreignkey")
    op.drop_constraint("iv_data__chip_state", "iv_data", type_="foreignkey")
    op.drop_index("ix_iv_data_chip_id", table_name="iv_data")
    op.drop_index("ix_iv_data_chip_state_id", table_name="iv_data")
    op.drop_column("iv_data", "chip_state_id")
    op.drop_column("iv_data", "temperature")
    op.drop_column("iv_data", "int_time")
    op.drop_column("iv_data", "chip_id")
    op.drop_column("iv_data", "datetime")


def downgrade() -> None:
    op.add_column(
        "iv_data",
        sa.Column(
            "datetime",
            mysql.DATETIME(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "iv_data",
        sa.Column("chip_id", mysql.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column("iv_data", sa.Column("int_time", mysql.VARCHAR(length=20), nullable=True))
    op.add_column("iv_data", sa.Column("temperature", mysql.FLOAT(), nullable=True))
    op.add_column(
        "iv_data",
        sa.Column("chip_state_id", mysql.INTEGER(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        "iv_data__chip_state",
        "iv_data",
        "chip_state",
        ["chip_state_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "iv_data__chip",
        "iv_data",
        "chip",
        ["chip_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.create_index("ix_iv_data_chip_state_id", "iv_data", ["chip_state_id"], unique=False)
    op.create_index("ix_iv_data_chip_id", "iv_data", ["chip_id"], unique=False)
