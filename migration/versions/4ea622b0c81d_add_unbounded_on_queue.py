"""add unbounded on queue

Revision ID: 4ea622b0c81d
Revises: 24a44075f9ce
Create Date: 2016-12-22 15:30:52.739696

"""

# revision identifiers, used by Alembic.
revision = '4ea622b0c81d'
down_revision = '24a44075f9ce'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('queues', sa.Column('unbounded', sa.Boolean, default=False))


def downgrade():
    op.drop_column('queues', 'unbounded')
