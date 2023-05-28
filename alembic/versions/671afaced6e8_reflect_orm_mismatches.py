"""Reflect ORM mismatches

Revision ID: 671afaced6e8
Revises: 99a5042c82da
Create Date: 2022-12-04 15:07:25.912429

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "671afaced6e8"
down_revision = "99a5042c82da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "cv_data",
        "voltage_input",
        existing_type=mysql.DECIMAL(precision=10, scale=5),
        nullable=False,
    )
    op.alter_column("cv_data", "capacitance", existing_type=mysql.FLOAT(), nullable=False)
    op.drop_constraint("cv_data_FK", "cv_data", type_="foreignkey")
    op.drop_constraint("cv_data_FK_1", "cv_data", type_="foreignkey")
    op.create_foreign_key("cv_data__chip", "cv_data", "chip", ["chip_id"], ["id"])
    op.create_foreign_key("cv_data__chip_state", "cv_data", "chip_state", ["chip_state_id"], ["id"])
    op.drop_constraint("iv_data_FK", "iv_data", type_="foreignkey")
    op.drop_constraint("chip_id_fk", "iv_data", type_="foreignkey")
    op.create_foreign_key("iv_data__chip", "iv_data", "chip", ["chip_id"], ["id"])
    op.create_foreign_key("iv_data__chip_state", "iv_data", "chip_state", ["chip_state_id"], ["id"])
    op.drop_constraint("chip_ibfk_1", "chip", type_="foreignkey")
    op.create_foreign_key("chip__wafer", "chip", "wafer", ["wafer_id"], ["id"])
    op.alter_column("iv_data", "chip_id", existing_type=mysql.INTEGER(), nullable=False)
    op.alter_column(
        "iv_data",
        "voltage_input",
        existing_type=mysql.DECIMAL(precision=10, scale=5),
        nullable=False,
    )
    op.alter_column("iv_data", "anode_current", existing_type=mysql.FLOAT(), nullable=False)
    op.alter_column("wafer", "name", existing_type=mysql.VARCHAR(length=20), nullable=False)
    op.alter_column("chip", "wafer_id", existing_type=mysql.INTEGER(), nullable=False)


def downgrade() -> None:
    op.alter_column("wafer", "name", existing_type=mysql.VARCHAR(length=20), nullable=True)
    op.alter_column("iv_data", "anode_current", existing_type=mysql.FLOAT(), nullable=True)
    op.alter_column(
        "iv_data",
        "voltage_input",
        existing_type=mysql.DECIMAL(precision=10, scale=5),
        nullable=True,
    )
    op.alter_column("iv_data", "chip_id", existing_type=mysql.INTEGER(), nullable=True)
    op.drop_constraint("cv_data__chip_state", "cv_data", type_="foreignkey")
    op.drop_constraint("cv_data__chip", "cv_data", type_="foreignkey")
    op.create_foreign_key(
        "cv_data_FK_1",
        "cv_data",
        "chip",
        ["chip_id"],
        ["id"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "cv_data_FK",
        "cv_data",
        "chip_state",
        ["chip_state_id"],
        ["id"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )
    op.create_foreign_key("chip_ibfk_1", "chip", "wafer", ["wafer_id"], ["id"])
    op.drop_constraint("iv_data__chip_state", "iv_data", type_="foreignkey")
    op.drop_constraint("iv_data__chip", "iv_data", type_="foreignkey")
    op.create_foreign_key("chip_id_fk", "iv_data", "chip", ["chip_id"], ["id"])
    op.create_foreign_key("iv_data_FK", "iv_data", "chip_state", ["chip_state_id"], ["id"])
    op.drop_constraint("chip__wafer", "chip", type_="foreignkey")
    op.create_foreign_key("chp_ibfk_1", "chip", "wafer", ["wafer_id"], ["id"])
    op.alter_column("cv_data", "capacitance", existing_type=mysql.FLOAT(), nullable=True)
    op.alter_column(
        "cv_data",
        "voltage_input",
        existing_type=mysql.DECIMAL(precision=10, scale=5),
        nullable=True,
    )
    op.alter_column("chip", "wafer_id", existing_type=mysql.INTEGER(), nullable=True)
