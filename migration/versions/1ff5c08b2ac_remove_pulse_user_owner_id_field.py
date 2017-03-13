"""remove pulse user 1 to many field

Revision ID: 1ff5c08b2ac
Revises: 4bd0784e2978
Create Date: 2017-01-26 14:29:25.399344

"""

# revision identifiers, used by Alembic.
revision = '1ff5c08b2ac'
down_revision = '4bd0784e2978'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()

    # Sqlite does not support dropping columns or constraints, so only do this
    # on "real" databases.  Locally, we re-create the databases on dbinit
    # anyway.  In addition: this field and constraint are a no-op since they're
    # not used anymore in the code.
    if bind.engine.name is not "sqlite":
        op.drop_constraint('pulse_users_owner_id_fkey', 'pulse_users', 'foreignkey')
        op.drop_column('pulse_users', 'owner_id')


def downgrade():
    op.add_column('pulse_users', sa.Column('owner_id', sa.Integer,
                                           sa.ForeignKey('users.id')))
