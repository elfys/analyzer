"""add client_version table

Revision ID: d9cf1337bbed
Revises: 110b185fbc52
Create Date: 2022-12-18 19:55:03.891845

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d9cf1337bbed"
down_revision = "110b185fbc52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    client_version_table = op.create_table(
        "client_version",
        sa.Column("version", sa.CHAR(length=10), nullable=False),
        sa.PrimaryKeyConstraint("version"),
        sa.UniqueConstraint("version"),
    )
    op.bulk_insert(
        client_version_table,
        [
            {"version": "0.16"},
        ],
    )


def downgrade() -> None:
    op.drop_table("client_version")
