# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import backref, relationship

from pulseguardian.model.base import Base, db_session
from pulseguardian.model.pulse_user import PulseUser


pulse_user_owners = Table('pulse_user_owners',
                          Base.metadata,
                          Column('users_id',
                                 Integer,
                                 ForeignKey('users.id')),
                          Column('pulse_users_id',
                                 Integer,
                                 ForeignKey('pulse_users.id')))


class User(Base):
    """Pulse Guardian User class, identified by an email address."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    admin = Column(Boolean)

    pulse_users = relationship(PulseUser, backref=backref('owners'),
                               cascade='save-update, merge, delete',
                               secondary=pulse_user_owners)

    # TODO: Remove this in a follow-up commit.  Needed for migration.
    old_pulse_users = relationship(PulseUser, backref='owner',
                                   cascade='save-update, merge, delete')


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
