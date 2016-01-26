# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from pulseguardian.model.base import Base, db_session
from pulseguardian.model.queue_notification import queue_notification


class Email(Base):
    """Email Class
    User and Queue notification emails
    """

    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)

    queue = relationship('Queue', secondary=queue_notification,
                         back_populates='notifications')

    def __repr__(self):
        return "<Email(email='{0}')>".format(self.email)

    __str__ = __repr__
