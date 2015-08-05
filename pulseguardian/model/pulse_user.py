# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pulseguardian import config
from pulseguardian.model.base import Base, db_session
from pulseguardian.model.queue import Queue


class PulseUser(Base):
    """User class, linked to a rabbitmq user (with the same username).
    Provides access to a user's queues.
    """

    __tablename__ = 'pulse_users'

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    username = Column(String(255), unique=True)

    queues = relationship(
        Queue, backref='owner', cascade='save-update, merge, delete')

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
