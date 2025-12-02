# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
from typing import List, TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulseguardian import config, management as pulse_management
from pulseguardian.model.base import Base, db_session

if TYPE_CHECKING:
    from pulseguardian.model.queue import Queue
    from pulseguardian.model.user import User


class RabbitMQAccount(Base):
    """User class, linked to a rabbitmq user (with the same username).
    Provides access to a user's queues.
    """

    __tablename__ = "pulse_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)

    queues: Mapped[List["Queue"]] = relationship(
        back_populates="owner", cascade="save-update, merge, delete"
    )

    owners: Mapped[List["User"]] = relationship(
        back_populates="rabbitmq_accounts", secondary="pulse_user_owners"
    )

    @staticmethod
    def new_user(username, password="", owners=None, create_rabbitmq_user=True):
        """Initializes a new account object, generating a salt and encrypting
        its password. Then creates a RabbitMQ user if needed and sets
        permissions.

        :param create_rabbitmq_user: Whether to add this user to the rabbitmq
        server via the management plugin.  Used by tests.
        """
        # Ensure that ``owners`` is a list.
        if owners and not isinstance(owners, list):
            owners = [owners]
        rabbitmq_account = RabbitMQAccount(owners=owners, username=username)

        if create_rabbitmq_user:
            rabbitmq_account._create_user(password)
            rabbitmq_account._set_permissions()

        db_session.add(rabbitmq_account)
        db_session.commit()

        return rabbitmq_account

    @staticmethod
    def strong_password(password):
        return (
            re.findall("[0-9]", password)
            and re.findall("[a-zA-Z]", password)
            and len(password) >= 6
        )

    def change_password(self, new_password):
        """ "Changes" a user's password by deleting his rabbitmq account
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
        read_perms = "^(queue/{0}/.*|exchange/.*)".format(esc_username)
        write_conf_perms = "^(queue/{0}/.*|exchange/{0}/.*)".format(esc_username)

        pulse_management.set_permission(
            username=self.username,
            vhost=config.rabbit_vhost,
            read=read_perms,
            configure=write_conf_perms,
            write=write_conf_perms,
        )

    def __repr__(self):
        return "<RabbitMQAccount(username='{0}', owners='{1}')>".format(
            self.username, ", ".join([owner.email for owner in self.owners])
        )

    __str__ = __repr__
