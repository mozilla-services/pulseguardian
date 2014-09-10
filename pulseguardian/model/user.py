# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import hashlib
import os
import re

from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.orm import relationship

from base import Base, db_session
from queue import Queue

def hash_password(password, salt):
    return hashlib.sha256(salt + password.encode('utf-8')).hexdigest()

class User(Base):
    """User class, linked to a rabbitmq user (with the same username)
    once activated. Provides access to a user's queues.
    """

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True)
    email = Column(String(100))
    salt = Column(String(100))
    secret_hash = Column(String(100), unique=True)
    admin = Column(Boolean)

    queues = relationship(
        Queue, backref='owner', cascade='save-update, merge, delete')

    @staticmethod
    def new_user(email, username, password, management_api, admin=False):
        """Initializes a new user, generating a salt and encrypting
        his password. Then creates a RabbitMQ user if needed and sets
        permissions.
        """
        email = email.lower()
        user = User(email=email, username=username, admin=admin)

        user.salt = os.urandom(14).encode('base_64')
        user.secret_hash = hash_password(password=password, salt=user.salt)

        if management_api is not None:
            # Creating the appropriate rabbitmq user if it doesn't already
            # exist.
            try:
                management_api.user(username)
            except management_api.exception:
                management_api.create_user(username=username, password=password)

            read_perms = '^(queue/{0}/.*|exchange/.*)'.format(username)
            write_conf_perms = '^(queue/{0}/.*|exchange/{0}/.*)'.format(username)

            management_api.set_permission(username=username,
                                          vhost='/',
                                          read=read_perms,
                                          configure=write_conf_perms,
                                          write=write_conf_perms)

        db_session.add(user)
        db_session.commit()

        return user

    @staticmethod
    def strong_password(password):
        return (re.findall('[0-9]', password) and
                re.findall('[a-zA-Z]', password) and len(password) > 6)

    def change_password(self, new_password, management_api):
        """"Changes" a user's password by deleting his rabbitmq account
        and recreating it with the new password.
        """
        try:
            management_api.delete_user(self.username)
        except management_api.exception:
            pass
        management_api.create_user(username=self.username, password=new_password)
        management_api.set_permission(username=self.username, vhost='/',
                                      read='.*', configure='.*', write='.*')

        self.salt = os.urandom(14).encode('base_64')
        self.secret_hash = hash_password(password=new_password, salt=self.salt)

        db_session.add(self)
        db_session.commit()

    def valid_password(self, password):
        return hash_password(password, self.salt) == self.secret_hash

    def __repr__(self):
        return "<User(email='{0}', username='{1}')>".format(self.email,
                                                            self.username)

    __str__ = __repr__
