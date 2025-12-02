# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import List, TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulseguardian.model.base import Base, db_session

if TYPE_CHECKING:
    from pulseguardian.model.pulse_user import RabbitMQAccount


rabbitmq_account_owners = Table(
    "pulse_user_owners",
    Base.metadata,
    Column("users_id", Integer, ForeignKey("users.id")),
    Column("pulse_users_id", Integer, ForeignKey("pulse_users.id")),
)


class User(Base):
    """Pulse Guardian User class, identified by an email address."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)

    rabbitmq_accounts: Mapped[List["RabbitMQAccount"]] = relationship(
        back_populates="owners",
        cascade="save-update, merge, delete",
        secondary=rabbitmq_account_owners,
    )

    @staticmethod
    def new_user(email, admin=False):
        """Initializes a new user, generating a salt and encrypting
        his password. Then creates a RabbitMQ user if needed and sets
        permissions.
        """
        email = email.lower()
        user = User(email=email, admin=admin)

        db_session.add(user)
        db_session.commit()

        return user

    def set_admin(self, is_admin):
        self.admin = is_admin
        db_session.commit()

    def __repr__(self):
        return "<User(email='{0}', admin='{1}')>".format(self.email, self.admin)

    __str__ = __repr__
