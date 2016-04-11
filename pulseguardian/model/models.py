import re

from sqlalchemy import (Boolean, Column, ForeignKey,
                        Integer, String, Table)
from sqlalchemy.orm import relationship

from pulseguardian import config
from pulseguardian.model.base import Base, db_session


class User(Base):
    """Pulse Guardian User class, identified by an email address."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey('emails.id'))
    admin = Column(Boolean)

    pulse_users = relationship('PulseUser', backref='owner',
                               cascade='save-update, merge, delete')

    email = relationship('Email', backref='user')

    @staticmethod
    def new_user(email_address, admin=False):
        """Initializes a new user, generating a salt and encrypting
        his password. Then creates a RabbitMQ user if needed and sets
        permissions.
        """
        email = Email.get_email(email_address)
        user = User(email=email, admin=admin)
        db_session.add(user)
        db_session.commit()

        return user

    @staticmethod
    def get_by_email(email):
        return User.query.filter(
            User.email.has(
                Email.address==email)).first();

    def __repr__(self):
        return "<User(email='{0}', admin='{1}')>".format(self.email,
                                                         self.admin)

    __str__ = __repr__


class PulseUser(Base):
    """User class, linked to a rabbitmq user (with the same username).
    Provides access to a user's queues.
    """

    __tablename__ = 'pulse_users'

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    username = Column(String(255), unique=True)

    queues = relationship('Queue', backref='owner',
                          cascade='save-update, merge, delete')

    @staticmethod
    def new_user(username, password='', owner=None, management_api=None):
        """Initializes a new user, generating a salt and encrypting
        his password. Then creates a RabbitMQ user if needed and sets
        permissions.
        """
        pulse_user = PulseUser(owner=owner, username=username)

        if management_api is not None:
            pulse_user._create_user(management_api, password)
            pulse_user._set_permissions(management_api)

        db_session.add(pulse_user)
        db_session.commit()

        return pulse_user

    @staticmethod
    def strong_password(password):
        return (re.findall('[0-9]', password) and
                re.findall('[a-zA-Z]', password) and len(password) >= 6)

    def change_password(self, new_password, management_api):
        """"Changes" a user's password by deleting his rabbitmq account
        and recreating it with the new password.
        """
        try:
            management_api.delete_user(self.username)
        except management_api.exception:
            pass

        self._create_user(management_api, new_password)
        self._set_permissions(management_api)

        db_session.add(self)
        db_session.commit()

    def _create_user(self, management_api, password):
        management_api.create_user(username=self.username, password=password)

    def _set_permissions(self, management_api):
        esc_username = re.escape(self.username)
        read_perms = '^(queue/{0}/.*|exchange/.*)'.format(esc_username)
        write_conf_perms = '^(queue/{0}/.*|exchange/{0}/.*)'.format(
            esc_username)

        management_api.set_permission(username=self.username,
                                      vhost=config.rabbit_vhost,
                                      read=read_perms,
                                      configure=write_conf_perms,
                                      write=write_conf_perms)

    def __repr__(self):
        return "<PulseUser(username='{0}', owner='{1}')>".format(self.username,
                                                                 self.owner)

    __str__ = __repr__


queue_notification = Table('queue_notifications', Base.metadata,
                           Column('queue_id', Integer, ForeignKey('queues.id')),
                           Column('email_id', Integer, ForeignKey('emails.id')))


class Queue(Base):
    __tablename__ = 'queues'

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    owner_id = Column(Integer, ForeignKey('pulse_users.id'), nullable=True)
    size = Column(Integer)
    warned = Column(Boolean)
    durable = Column(Boolean, nullable=False, default=False)

    notifications = relationship('Email',
                                 secondary=queue_notification,
                                 back_populates='queues')

    @staticmethod
    def notification_exists(queue, email):
        return Queue.query.filter(
            Queue.notifications.any(
                Email.address==email)) \
                   .filter(Queue.id==queue).count()

    @staticmethod
    def notification_delete(queue, email):
        queue_obj = Queue.query.filter(Queue.id==queue).first()
        queue_obj.notifications.remove(Email.get_email(email))
        db_session.commit()

        user = User.get_by_email(email)
        notification = Queue.query.filter(
            Queue.notifications.any(Email.address==email)).count()
        if not user and not notification:
            db_session.delete(Email.get_email(email))

        db_session.commit()

    @staticmethod
    def create_notification(queue, email):
        queue_obj = Queue.query.filter(Queue.id==queue).first()
        queue_obj.notifications.append(Email.get_email(email))
        db_session.add(queue_obj)
        db_session.commit()

    @staticmethod
    def get_notifications(queue):
        return Email.query.filter(
            Email.queues.any(Queue.name==queue)).all()

    def __repr__(self):
        return "<Queue(name='{0}', owner='{1}')>".format(self.name, self.owner)

    __str__ = __repr__


class Email(Base):
    """Email Class
    User and Queue notification emails
    """

    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    address = Column(String(255), unique=True, nullable=False)

    queues = relationship('Queue', secondary=queue_notification,
                        back_populates='notifications')

    @staticmethod
    def get_email(address):
        query = Email.query.filter(Email.address==address)
        if query.count():
            email = query.first()
        else:
            email = Email(address=address)

        return email

    def __repr__(self):
        return "<Email(address='{0}')>".format(self.address)

    __str__ = __repr__
