# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base

sys.path.append('..')
from pulseguardian import config, mozdef

Base = declarative_base()
engine = create_engine(config.database_url,
                       pool_recycle=config.pool_recycle_interval,
                       convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base.query = db_session.query_property()


def init_db():
    while True:
        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError as e:
            mozdef.log(
                mozdef.NOTICE,
                mozdef.STARTUP,
                'Failed to connect to database.  Retrying...',
                details={
                    'error': str(e),
                },
            )
            time.sleep(5)
        else:
            break
