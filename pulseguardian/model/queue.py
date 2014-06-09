# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey

from base import Base


class Queue(Base):
    __tablename__ = 'queues'

    name = Column(String(40), primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id'))
    size = Column(Integer)

    warned = Column(Boolean)

    def __repr__(self):
        return "<Queue(name='{0}', owner='{1}')>".format(self.name, self.owner)

    __str__ = __repr__
