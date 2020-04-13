"""Create pulse_user_owners table. Create keys for other tables.

Revision ID: 4bd0784e2978
Revises:
Create Date: 2016-01-11 08:44:00.365481

"""

from alembic import op
from sqlalchemy.orm import Session
import sqlalchemy as sa

from pulseguardian.model.pulse_user import PulseUser
# Must import these, even if they are not directly used.  Importing
# them allows alembic to be able to use the relationships of ``owner`` and
# ``owners`` to the User and pulse_user_owners tables.
from pulseguardian.model.user import User, pulse_user_owners

# revision identifiers, used by Alembic.
revision = '4bd0784e2978'
down_revision = '4ea622b0c81d'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    op.create_table(
        'pulse_user_owners',
        sa.Column('users_id', sa.Integer, sa.ForeignKey('users.id'),
                  nullable=False),
        sa.Column('pulse_users_id', sa.Integer,
                  sa.ForeignKey('pulse_users.id'), nullable=False),
    )

    # Migrate existing single owners to the multiple owners table.
    for pulse_user in session.query(PulseUser):
        pulse_user.owners = list([pulse_user.owner])

    session.commit()


def downgrade():
    op.drop_table('pulse_user_owners')
