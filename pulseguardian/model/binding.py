# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pulseguardian.model.base import Base


class Binding(Base):
    __tablename__ = "bindings"

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(255))
    routing_key: Mapped[str] = mapped_column(String(255))
    queue_name: Mapped[str] = mapped_column(String(255), ForeignKey("queues.name"))

    @property
    def name(self):
        return Binding.as_string(self.exchange, self.routing_key)

    @staticmethod
    def as_string(exchange, routing_key):
        # make this available so functions outside this class will
        # be consistent with the string format for comparisons.
        return "{}-{}".format(exchange, routing_key)

    def __repr__(self):
        return "<Binding(exchange='{0}', routing_key='{1}')>".format(
            self.exchange, self.routing_key
        )

    __str__ = __repr__
