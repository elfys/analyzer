"""add iv_conditions.instrument_id

Revision ID: 87540ed003e1
Revises: 2ce46d2cc9fc
Create Date: 2023-02-07 14:51:28.277825

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "87540ed003e1"
down_revision = "2ce46d2cc9fc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("iv_conditions", sa.Column("instrument_id", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "iv_conditions__instrument",
        "iv_conditions",
        "instrument",
        ["instrument_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )

    conn: Connection = op.get_bind()

    res = conn.execute(
        text(
            """
    INSERT INTO `instrument` (name) VALUES
        ('EPG'),
        ('Keithley SMU 2636 (Innopoli)'),
        ('Keithley SMU 4156 (Micronova)');
    """
        )
    )
    epg, innopoli, micronova = tuple(range(res.lastrowid, res.lastrowid + 3))

    for voltages, instrument_id in (
        ((-0.75, 0.75, 100), epg),
        ((-6, -10, -20), innopoli),
        ((6, 10, 20, 0.009), micronova),
    ):
        conn.execute(
            text(
                """
        UPDATE iv_conditions c
        SET c.instrument_id = :instrument_id
        WHERE
            c.instrument_id IS NULL
            AND
            c.id IN (SELECT DISTINCT conditions_id FROM iv_data WHERE voltage_input IN :voltages)
        """
            ).bindparams(voltages=voltages, instrument_id=instrument_id)
        )

    conn.execute(
        text(
            """
    UPDATE iv_conditions c
    SET c.instrument_id = :instrument_id
    WHERE c.instrument_id IS NULL AND c.id in (
        SELECT d.conditions_id
        FROM iv_data d
        GROUP BY d.conditions_id HAVING COUNT(d.id) = 3)
    """
        ).bindparams(instrument_id=innopoli)
    )


def downgrade() -> None:
    op.drop_constraint("iv_conditions__instrument", "iv_conditions", type_="foreignkey")
    op.drop_column("iv_conditions", "instrument_id")
