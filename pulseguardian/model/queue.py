# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulseguardian.model.base import Base
from pulseguardian.model.binding import Binding
from pulseguardian.model.pulse_user import RabbitMQAccount


class Queue(Base):
    __tablename__ = "queues"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pulse_users.id"), nullable=True
    )
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # whether the queue can grow beyond the deletion size without being deleted
    unbounded: Mapped[bool] = mapped_column(Boolean, default=False)
    warned: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    durable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    bindings: Mapped[List["Binding"]] = relationship(
        cascade="save-update, merge, delete"
    )
    owner: Mapped[Optional["RabbitMQAccount"]] = relationship(back_populates="queues")

    def __repr__(self):
        return "<Queue(name='{0}', owner='{1}')>".format(self.name, self.owner)

    __str__ = __repr__
