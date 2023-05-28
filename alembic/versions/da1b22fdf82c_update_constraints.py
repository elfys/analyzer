"""Rename and add new constraints

Revision ID: da1b22fdf82c
Revises: 671afaced6e8
Create Date: 2022-12-07 21:30:21.444366

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "da1b22fdf82c"
down_revision = "671afaced6e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_chip_wafer_id"), "chip", ["wafer_id"], unique=False)
    op.drop_constraint("chip__wafer", "chip", type_="foreignkey")
    op.create_foreign_key(
        "chip__wafer",
        "chip",
        "wafer",
        ["wafer_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )
    op.drop_constraint("cv_data__chip", "cv_data", type_="foreignkey")
    op.drop_constraint("cv_data__chip_state", "cv_data", type_="foreignkey")
    op.create_foreign_key(
        "cv_data__chip",
        "cv_data",
        "chip",
        ["chip_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "cv_data__chip_state",
        "cv_data",
        "chip_state",
        ["chip_state_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_cv_data_chip_id"), "cv_data", ["chip_id"], unique=False)
    op.create_index(op.f("ix_cv_data_chip_state_id"), "cv_data", ["chip_state_id"], unique=False)
    op.drop_constraint("iv_data__chip_state", "iv_data", type_="foreignkey")
    op.drop_constraint("iv_data__chip", "iv_data", type_="foreignkey")
    op.create_foreign_key(
        "iv_data__chip",
        "iv_data",
        "chip",
        ["chip_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
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
    op.create_index(op.f("ix_iv_data_chip_id"), "iv_data", ["chip_id"], unique=False)
    op.create_index(op.f("ix_iv_data_chip_state_id"), "iv_data", ["chip_state_id"], unique=False)
    op.create_unique_constraint("unique_chip", "chip", ["name", "wafer_id"])
    op.create_unique_constraint("chip_state_name", "chip_state", ["name"])
    op.create_unique_constraint("wafer_name", "wafer", ["name"])


def downgrade() -> None:
    op.drop_constraint("iv_data__chip_state", "iv_data", type_="foreignkey")
    op.drop_constraint("iv_data__chip", "iv_data", type_="foreignkey")
    op.drop_constraint("wafer_name", "wafer", type_="unique")
    op.drop_constraint("chip_state_name", "chip_state", type_="unique")
    op.drop_constraint("cv_data__chip_state", "cv_data", type_="foreignkey")
    op.drop_constraint("cv_data__chip", "cv_data", type_="foreignkey")
    op.drop_constraint("chip__wafer", "chip", type_="foreignkey")
    op.drop_constraint("unique_chip", "chip", type_="unique")
    op.drop_index(op.f("ix_iv_data_chip_state_id"), table_name="iv_data")
    op.drop_index(op.f("ix_iv_data_chip_id"), table_name="iv_data")
    op.drop_index(op.f("ix_cv_data_chip_state_id"), table_name="cv_data")
    op.drop_index(op.f("ix_cv_data_chip_id"), table_name="cv_data")
    op.drop_index(op.f("ix_chip_wafer_id"), table_name="chip")
    op.create_foreign_key("iv_data__chip", "iv_data", "chip", ["chip_id"], ["id"])
    op.create_foreign_key(
        "iv_data__chip_state",
        "iv_data",
        "chip_state",
        ["chip_state_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "cv_data__chip_state",
        "cv_data",
        "chip_state",
        ["chip_state_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key("cv_data__chip", "cv_data", "chip", ["chip_id"], ["id"])
    op.create_foreign_key("chip__wafer", "chip", "wafer", ["wafer_id"], ["id"], ondelete="RESTRICT")
