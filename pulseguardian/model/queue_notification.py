from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table

from pulseguardian.model.base import Base

queue_notification = Table('queue_notifications', Base.metadata,
                           Column('id', Integer, primary_key=True),
                           Column('queue_name', String(255), ForeignKey('queues.name')),
                           Column('email_id', Integer, ForeignKey('emails.id')))
