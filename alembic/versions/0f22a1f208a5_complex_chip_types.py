"""complex chip_types

Revision ID: 0f22a1f208a5
Revises: 9319f9d2c2a9
Create Date: 2023-08-04 11:02:48.835956

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0f22a1f208a5'
down_revision = '9319f9d2c2a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("chip", "type")
    op.add_column('chip', sa.Column('type', sa.String(length=8), nullable=True))
    op.execute("UPDATE chip SET type = SUBSTR(`name`,1,1) WHERE name REGEXP '^[a-zA-Z][0-9]{4}'")
    op.execute("UPDATE chip SET type = CONCAT(SUBSTR(`name`,1,1), 'H') WHERE name REGEXP '^[a-zA-Z]H[0-9]{4}'")
    op.execute("UPDATE chip SET type = 'TS' WHERE test_structure = 1")
    op.execute(
        "UPDATE chip SET type = 'REF' WHERE wafer_id = (SELECT id FROM wafer WHERE name = 'REF')")
    op.create_index(op.f('ix_chip_type'), 'chip', ['type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chip_type'), table_name='chip')
    op.drop_column("chip", "type")
    op.add_column('chip',
                  sa.Column('type', sa.CHAR(length=1), nullable=True,
                            server_default=sa.text("(SUBSTR(`name`,1,1))")))
