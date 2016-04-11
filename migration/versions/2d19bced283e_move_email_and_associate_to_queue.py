"""Move email and associate to queue

Revision ID: 2d19bced283e
Revises: 641f40e01a9
Create Date: 2016-01-15 15:36:50.939484

"""

# revision identifiers, used by Alembic.
revision = '2d19bced283e'
down_revision = ''
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.sql import select, insert, update, text
from sqlalchemy.schema import Sequence, CreateSequence

from pulseguardian.model.base import engine
from pulseguardian.model.models import User, Email, queue_notification


def upgrade():
    op.drop_constraint('queues_pkey', 'queues')
    op.execute(CreateSequence(Sequence('queues_id_seq')))
    op.add_column('queues', Column('id', Integer,
                                   server_default=text("nextval('queues_id_seq'::regclass)")))
    op.create_primary_key('queues_pkey', 'queues', ['id'])

    Email.__table__.create(bind=engine)
    op.create_table(
        'queue_notifications',
        Column('queue_id', Integer, ForeignKey('queues.id')),
        Column('email_id', Integer, ForeignKey('emails.id'))
    )
    op.add_column('users', Column('email_id', Integer,
                                  ForeignKey('emails.id')))

    conn = op.get_bind()
    s = select([text("users.email")]).select_from(text("users"))
    users = conn.execute(s)
    table_user = User.__table__
    for row in users:
       ins = Email.__table__.insert().values(address=row['email'])
       result_insert_email = conn.execute(ins) 
       upd = table_user \
             .update() \
             .values(email_id=result_insert_email.inserted_primary_key[0]) \
             .where(text('users.email = :email'))
       conn.execute(upd, email=row['email'])

    op.drop_column('users', 'email')

def downgrade():
    op.drop_constraint('queue_notifications_email_id_fkey', 'queue_notifications')
    op.drop_constraint('queue_notifications_queue_name_fkey', 'queue_notifications')
    op.drop_table('queue_notifications')
    op.drop_column('users', 'email_id')
    op.drop_table('emails')
