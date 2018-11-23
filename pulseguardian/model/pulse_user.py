# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from pulseguardian import config, management as pulse_management
from pulseguardian.model.base import Base, db_session
from pulseguardian.model.queue import Queue


class PulseUser(Base):
    """User class, linked to a rabbitmq user (with the same username).
    Provides access to a user's queues.
    """

    __tablename__ = 'pulse_users'

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True)

    queues = relationship(
        Queue, backref='owner', cascade='save-update, merge, delete')

    @staticmethod
    def new_user(username, password='', owners=None, create_rabbitmq_user=True):
        """Initializes a new user, generating a salt and encrypting
        his password. Then creates a RabbitMQ user if needed and sets
        permissions.

        :param create_rabbitmq_user: Whether to add this user to the rabbitmq
        server via the management plugin.  Used by tests.
        """
        # Ensure that ``owners`` is a list.
        if owners and not isinstance(owners, list):
            owners = [owners]
        pulse_user = PulseUser(owners=owners, username=username)

        if create_rabbitmq_user:
            pulse_user._create_user(password)
            pulse_user._set_permissions()

        db_session.add(pulse_user)
        db_session.commit()

        return pulse_user

    @staticmethod
    def strong_password(password):
        return (re.findall('[0-9]', password) and
                re.findall('[a-zA-Z]', password) and len(password) >= 6)

    def change_password(self, new_password):
        """"Changes" a user's password by deleting his rabbitmq account
        and recreating it with the new password.
        """
        try:
            pulse_management.delete_user(self.username)
        except pulse_management.PulseManagementException:
            pass

        self._create_user(new_password)
        self._set_permissions()

        db_session.add(self)
        db_session.commit()

    def _create_user(self, password):
        pulse_management.create_user(username=self.username, password=password)

    def _set_permissions(self):
        esc_username = re.escape(self.username)
        read_perms = '^(queue/{0}/.*|exchange/.*)'.format(esc_username)
        write_conf_perms = '^(queue/{0}/.*|exchange/{0}/.*)'.format(
            esc_username)

        pulse_management.set_permission(username=self.username,
                                        vhost=config.rabbit_vhost,
                                        read=read_perms,
                                        configure=write_conf_perms,
                                        write=write_conf_perms)

    def __repr__(self):
        return "<PulseUser(username='{0}', owners='{1}')>".format(
            self.username,
            ', '.join([owner.email for owner in self.owners]))

    __str__ = __repr__
