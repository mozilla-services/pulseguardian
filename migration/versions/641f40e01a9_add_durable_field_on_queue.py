"""Add durable field on queue

Revision ID: 641f40e01a9
Revises:
Create Date: 2015-12-13 14:43:46.493374

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "641f40e01a9"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("queues", sa.Column("durable", sa.Boolean))


def downgrade():
    op.drop_column("queues", "durable")
