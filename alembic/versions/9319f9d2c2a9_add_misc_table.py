"""add misc table

Revision ID: 9319f9d2c2a9
Revises: 84438e320041
Create Date: 2023-05-28 11:14:48.643266

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '9319f9d2c2a9'
down_revision = '84438e320041'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('misc',
                    sa.Column('name', sa.VARCHAR(length=100), nullable=False),
                    sa.Column('data', sa.JSON(), nullable=False),
                    sa.PrimaryKeyConstraint('name')
                    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('misc')
    # ### end Alembic commands ###
