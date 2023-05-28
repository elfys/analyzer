"""add IV conditions

Revision ID: 2ce46d2cc9fc
Revises: ea3696fd0d5a
Create Date: 2023-02-02 18:48:17.751028

"""
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "2ce46d2cc9fc"
down_revision = "ea3696fd0d5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iv_conditions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chip_id", sa.Integer(), nullable=False),
        sa.Column("chip_state_id", sa.Integer(), nullable=False),
        sa.Column(
            "datetime",
            sa.DATETIME(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("int_time", sa.VARCHAR(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["chip_id"],
            ["chip.id"],
            name="iv_conditions__chip",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chip_state_id"],
            ["chip_state.id"],
            name="iv_conditions__chip_state",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_iv_conditions_chip_id"), "iv_conditions", ["chip_id"], unique=False)
    op.create_index(
        op.f("ix_iv_conditions_chip_state_id"),
        "iv_conditions",
        ["chip_state_id"],
        unique=False,
    )
    op.add_column("iv_data", sa.Column("conditions_id", sa.Integer()))

    datetime_round_factor = 3600 * 8
    temperature_round_digits = 1
    threshold_number = 66
    conn: Connection = op.get_bind()
    conn.execution_options(autocommit=True)
    rows_to_update = conn.execute(
        text("SELECT COUNT(1) FROM iv_data WHERE conditions_id is NULL")
    ).scalar()

    logger = logging.getLogger("alembic.runtime.migration")
    logger.info("Start adding iv_conditions rows")
    while rows_to_update > 0:
        logger.info(f"round_factor={datetime_round_factor}, rows_to_update={rows_to_update}")
        conn.execute(
            text(
                """
        INSERT INTO iv_conditions (chip_id, chip_state_id, temperature, int_time, datetime)
        SELECT T.chip_id, T.chip_state_id, T.r_temperature, T.int_time, T.rounded_datetime FROM (
            SELECT count(1) as cnt,
            chip_id,
            chip_state_id,
            ROUND(temperature, :temperature_round_digits) as r_temperature,
            int_time,
            FROM_UNIXTIME(ROUND(UNIX_TIMESTAMP(datetime) / :round_factor) * :round_factor) AS rounded_datetime
            FROM iv_data
            WHERE conditions_id is NULL
            GROUP BY chip_id, chip_state_id, int_time, rounded_datetime, r_temperature
        ) as T WHERE T.cnt <= :threshold_number
        """
            ).bindparams(
                round_factor=datetime_round_factor,
                threshold_number=threshold_number,
                temperature_round_digits=temperature_round_digits,
            )
        )

        conn.execute(
            text(
                """
        UPDATE iv_data d
        JOIN iv_conditions c
        ON
            d.chip_id = c.chip_id
            AND d.chip_state_id = c.chip_state_id
            AND FROM_UNIXTIME(ROUND(UNIX_TIMESTAMP(d.datetime) / :round_factor) * :round_factor) = c.datetime
            AND d.int_time = c.int_time
            AND (
                ABS(ROUND(d.temperature, :temperature_round_digits) - c.temperature) < 0.001
                OR
                d.temperature IS NULL AND c.temperature IS NULL
            )
        SET d.conditions_id = c.id
        WHERE d.conditions_id is NULL
        """
            ).bindparams(
                round_factor=datetime_round_factor,
                temperature_round_digits=temperature_round_digits,
            )
        )

        datetime_round_factor = int(datetime_round_factor / 2)

        rows_to_update = conn.execute(
            text("SELECT COUNT(1) FROM iv_data WHERE conditions_id is NULL")
        ).scalar()

    logger.info("All iv_conditions are created. Adjusting datetime values")
    conn.execute(
        text(
            """
    UPDATE iv_conditions c
    JOIN (
        SELECT conditions_id, FROM_UNIXTIME(ROUND(AVG(UNIX_TIMESTAMP(datetime)))) AS avg_datetime, AVG(temperature) AS avg_temperature
        FROM iv_data GROUP BY conditions_id
    ) AS d
    ON d.conditions_id = c.id
    SET c.datetime = d.avg_datetime, c.temperature = d.avg_temperature
    """
        )
    )

    op.alter_column("iv_data", "conditions_id", existing_type=mysql.INTEGER(), nullable=False)
    op.create_foreign_key(
        "iv_data__conditions",
        "iv_data",
        "iv_conditions",
        ["conditions_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.alter_column("iv_data", "chip_id", existing_type=mysql.INTEGER(), nullable=True)
    op.alter_column("iv_data", "chip_state_id", existing_type=mysql.INTEGER(), nullable=True)
    op.create_index(op.f("ix_iv_data_conditions_id"), "iv_data", ["conditions_id"], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("iv_data__conditions", "iv_data", type_="foreignkey")
    op.drop_index(op.f("ix_iv_data_conditions_id"), table_name="iv_data")
    op.drop_column("iv_data", "conditions_id")
    op.drop_constraint("iv_conditions__chip", "iv_conditions", type_="foreignkey")
    op.drop_constraint("iv_conditions__chip_state", "iv_conditions", type_="foreignkey")
    op.drop_index(op.f("ix_iv_conditions_chip_state_id"), table_name="iv_conditions")
    op.drop_index(op.f("ix_iv_conditions_chip_id"), table_name="iv_conditions")
    op.drop_table("iv_conditions")
    # ### end Alembic commands ###
