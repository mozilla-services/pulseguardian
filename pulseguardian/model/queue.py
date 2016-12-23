# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pulseguardian.model.base import Base
from pulseguardian.model.binding import Binding


class Queue(Base):
    __tablename__ = 'queues'

    name = Column(String(255), primary_key=True)
    owner_id = Column(Integer, ForeignKey('pulse_users.id'), nullable=True)
    size = Column(Integer)
    # whether the queue can grow beyond the deletion size without being deleted
    unbounded = Column(Boolean, default=False)

    warned = Column(Boolean)

    durable = Column(Boolean, nullable=False, default=False)
    bindings = relationship(Binding, cascade='save-update, merge, delete')


    def __repr__(self):
        return "<Queue(name='{0}', owner='{1}')>".format(self.name, self.owner)

    __str__ = __repr__
