"""Turn all IV measurements to the same voltages sign

Revision ID: 02d18a4cafc5
Revises: 76cc9bcdd45c
Create Date: 2023-03-26 21:07:59.638263

"""
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "02d18a4cafc5"
down_revision = "76cc9bcdd45c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn: Connection = op.get_bind()
    innopoli_instrument = conn.execute(
        text("SELECT id FROM instrument WHERE name LIKE '%Innopoli%'")
    ).scalar()
    op.execute(
        text(
            """
    UPDATE iv_data d
        SET d.voltage_input = -d.voltage_input
        WHERE d.conditions_id in (
            SELECT c.id
            FROM iv_conditions c
            WHERE c.instrument_id = :instrument_id)
    """
        ).bindparams(instrument_id=innopoli_instrument)
    )


def downgrade() -> None:
    upgrade()  # does effectively the same
