# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker
from sqlalchemy.exc import OperationalError

sys.path.append("..")
from pulseguardian import config, mozdef


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models with convenience query methods."""

    @classmethod
    def get_by(cls, **kwargs):
        """Convenience method for filter_by queries.

        Example: User.get_by(email='test@example.com')
        """
        stmt = select(cls)
        for key, value in kwargs.items():
            stmt = stmt.where(getattr(cls, key) == value)
        return db_session.execute(stmt).scalar_one_or_none()

    @classmethod
    def get_all(cls):
        """Get all records for this model."""
        return db_session.execute(select(cls)).scalars().all()


engine = create_engine(
    config.database_url,
    pool_recycle=config.pool_recycle_interval,
)

db_session = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
)


def init_db():
    while True:
        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError as e:
            mozdef.log(
                mozdef.NOTICE,
                mozdef.STARTUP,
                "Failed to connect to database.  Retrying...",
                details={
                    "error": str(e),
                },
            )
            time.sleep(5)
        else:
            break
