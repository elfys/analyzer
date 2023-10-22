"""add guard_current column

Revision ID: f440dd8943b7
Revises: 0f22a1f208a5
Create Date: 2023-10-23 15:55:55.914070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f440dd8943b7'
down_revision = '0f22a1f208a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('iv_data', sa.Column('guard_current', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('iv_data', 'guard_current')
