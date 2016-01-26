# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from pulseguardian.model.base import Base, db_session
from pulseguardian.model.pulse_user import PulseUser
from pulseguardian.model.email import Email


class User(Base):
    """Pulse Guardian User class, identified by an email address."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey('emails.id'))
    admin = Column(Boolean)

    pulse_users = relationship(PulseUser, backref='owner',
                               cascade='save-update, merge, delete')

    email = relationship(Email, uselist=False)

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

    def __repr__(self):
        return "<User(email='{0}', admin='{1}')>".format(self.email,
                                                         self.admin)

    __str__ = __repr__
