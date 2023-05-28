"""Initial migration

Revision ID: 99a5042c82da
Revises: None
Create Date: 2022-12-04 14:57:04.067939

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "99a5042c82da"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    chip_state_table = op.create_table(
        "chip_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "name",
            sa.VARCHAR(length=100),
            nullable=False,
            comment="Chip state is used to indicate the state of corresponding chip during measurement (iv_data)",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "wafer",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=20), nullable=True),
        sa.Column(
            "record_created_at",
            sa.DATETIME(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("batch_id", sa.VARCHAR(length=10), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "chip",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wafer_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.VARCHAR(length=20), nullable=False),
        sa.Column(
            "type",
            sa.CHAR(length=1),
            nullable=True,
            server_default=sa.text("(SUBSTR(`name`,1,1))"),
        ),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafer.id"], name="chip_ibfk_1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cv_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chip_id", sa.Integer(), nullable=False),
        sa.Column("chip_state_id", sa.Integer(), nullable=False),
        sa.Column("voltage_input", sa.DECIMAL(precision=10, scale=5), nullable=True),
        sa.Column("capacitance", sa.Float(), nullable=True),
        sa.Column(
            "datetime",
            sa.DATETIME(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["chip_id"], ["chip.id"], name="cv_data_FK_1"),
        sa.ForeignKeyConstraint(["chip_state_id"], ["chip_state.id"], name="cv_data_FK"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "iv_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chip_id", sa.Integer(), nullable=True),
        sa.Column("chip_state_id", sa.Integer(), nullable=False),
        sa.Column("int_time", sa.VARCHAR(length=20), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("voltage_input", sa.DECIMAL(precision=10, scale=5), nullable=True),
        sa.Column("anode_current", sa.Float(), nullable=True),
        sa.Column("cathode_current", sa.Float(), nullable=True),
        sa.Column("anode_current_corrected", sa.Float(), nullable=True),
        sa.Column(
            "datetime",
            sa.DATETIME(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["chip_id"], ["chip.id"], name="chip_id_fk"),
        sa.ForeignKeyConstraint(["chip_state_id"], ["chip_state.id"], name="iv_data_FK"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.bulk_insert(
        chip_state_table,
        [
            dict(id=1, name="before wafer dicing"),
            dict(id=2, name="after wafer dicing"),
            dict(id=3, name="after die bonding"),
            dict(id=4, name="after wire bonding"),
            dict(id=5, name="after optical epoxy"),
            dict(id=6, name="after PCB dicing"),
            dict(id=7, name="after resist removal"),
            dict(id=8, name="after TO-can with glass packaging"),
            dict(id=9, name="after TO-can no glass packaging"),
            dict(id=10, name="after TO-can with ball lens packaging"),
            dict(id=11, name="after glob-topping"),
            dict(id=12, name="after reflow"),
        ],
    )


def downgrade() -> None:
    op.drop_table("iv_data")
    op.drop_table("cv_data")
    op.drop_table("chip")
    op.drop_table("wafer")
    op.drop_table("chip_state")
