"""eqe orm

Revision ID: 110b185fbc52
Revises: da1b22fdf82c
Create Date: 2022-12-08 15:33:44.228517

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "110b185fbc52"
down_revision = "da1b22fdf82c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    carrier_table = op.create_table(
        "carrier",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "eqe_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DATE(), server_default=sa.text("(CURRENT_DATE)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    instrument_table = op.create_table(
        "instrument",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "eqe_conditions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chip_id", sa.Integer(), nullable=False),
        sa.Column("chip_state_id", sa.Integer(), nullable=False),
        sa.Column(
            "datetime",
            sa.DATETIME(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("bias", sa.Float(), nullable=False),
        sa.Column("averaging", sa.Integer(), nullable=False),
        sa.Column("dark_current", sa.Float(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("ddc", sa.VARCHAR(length=100), nullable=True),
        sa.Column("calibration_file", sa.VARCHAR(length=100), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.SmallInteger(), nullable=True),
        sa.Column("carrier_id", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(
            ["carrier_id"],
            ["carrier.id"],
            name="eqe_conditions__carrier",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chip_id"],
            ["chip.id"],
            name="eqe_conditions__chip",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chip_state_id"],
            ["chip_state.id"],
            name="eqe_conditions__chip_state",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instrument.id"],
            name="eqe_conditions__instrument",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["eqe_session.id"],
            name="eqe_conditions__session",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eqe_conditions_chip_id"), "eqe_conditions", ["chip_id"], unique=False)
    op.create_index(
        op.f("ix_eqe_conditions_chip_state_id"),
        "eqe_conditions",
        ["chip_state_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_eqe_conditions_session_id"),
        "eqe_conditions",
        ["session_id"],
        unique=False,
    )
    op.create_table(
        "eqe_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wavelength", sa.Integer(), nullable=False),
        sa.Column("light_current", sa.Float(), nullable=False),
        sa.Column("dark_current", sa.Float(), nullable=True),
        sa.Column("std", sa.Float(), nullable=True),
        sa.Column("eqe", sa.Float(), nullable=True),
        sa.Column("responsivity", sa.Float(), nullable=True),
        sa.Column("conditions_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conditions_id"],
            ["eqe_conditions.id"],
            name="eqe_data__conditions",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eqe_data_conditions_id"), "eqe_data", ["conditions_id"], unique=False)
    op.create_unique_constraint("instrument_name", "instrument", ["name"])
    op.create_unique_constraint("carrier_name", "carrier", ["name"])

    op.bulk_insert(
        carrier_table,
        [
            dict(name="Evaluation PCB"),
            dict(name="ESA PCB V1"),
            dict(name="ESA PCB V2"),
            dict(name="ESA PCB V3"),
            dict(name="Ceramic"),
            dict(name="TO-can"),
            dict(name="PD module V1"),
            dict(name="PD module V2"),
            dict(name="PD module V3"),
            dict(name="XG lab PCB"),
            dict(name="Commercial"),
        ],
    )
    op.bulk_insert(
        instrument_table,
        [
            dict(name="Keithley237"),
            dict(name="XTRALIEN"),
        ],
    )


def downgrade() -> None:
    op.drop_table("eqe_data")
    op.drop_table("eqe_conditions")
    op.drop_table("instrument")
    op.drop_table("eqe_session")
    op.drop_table("carrier")
