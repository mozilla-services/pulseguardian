import os
import hashlib

from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship

from base import Base, db_session
from queue import Queue


def hash_password(password, salt):
    return hashlib.sha512(salt + password).hexdigest()


class User(Base):
    __tablename__ = 'users'

    username = Column(String(100), unique=True)
    email = Column(String(100), primary_key=True)

    # Only stored temporarly
    password = Column(String(100))

    secret_hash = Column(String(200))
    salt = Column(String(100))

    activation_token = Column(String(100))
    activated = Column(Boolean)
    admin = Column(Boolean)

    queues = relationship(
        Queue, backref='owner', cascade='save-update, merge, delete')

    def valid_password(self, password):
        return hash_password(password, self.salt) == self.secret_hash

    def activate(self, management_api):
        self.activated = True
        # Creating the appropriate rabbitmq user
        management_api.create_user(
            username=self.username, password=self.password)
        # TODO : remove configure and write permissions while letting users
        # create queues ?
        management_api.set_permission(username=self.username, vhost='/',
                                      read='.*', configure='.*', write='.*')
        # Removing the user's password as it's no longer needed
        self.password = None

        db_session.add(self)
        db_session.commit()

    @staticmethod
    def new_user(email, username, password, admin=False):
        username = username.lower()
        password = password.lower()

        token = os.urandom(16).encode('hex')
        user = User(email=email, username=username,
                    activation_token=token, admin=admin, activated=False)

        # Temporarly storing the password, removed at activation
        user.password = password

        # Encrypting password
        user.salt = os.urandom(16).encode('base_64')
        user.secret_hash = hash_password(password, user.salt)

        return user

    def __repr__(self):
        return "<User(email='{}', username='{}')>".format(self.email, self.username)

    __str__ = __repr__
