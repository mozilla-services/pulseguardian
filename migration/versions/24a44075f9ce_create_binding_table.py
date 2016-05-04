"""create Binding table

Revision ID: 24a44075f9ce
Revises: 641f40e01a9
Create Date: 2016-05-10 11:52:34.849762

"""

# revision identifiers, used by Alembic.
revision = '24a44075f9ce'
down_revision = '641f40e01a9'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'bindings',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('exchange', sa.String(255)),
        sa.Column('routing_key', sa.String(255)),
        sa.Column('queue_name', sa.Unicode(255), sa.ForeignKey('queues.name')),
    )


def downgrade():
    op.drop_table('bindings')
