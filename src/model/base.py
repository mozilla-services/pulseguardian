import sys
sys.path.append('..')

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import config

db_signature = 'mysql://{}:{}@localhost/{}'.format(config.mysql_user, config.mysql_password, config.mysql_dbname)
engine = create_engine(db_signature, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    Base.metadata.create_all(bind=engine)

def clear_db():
    Base.metadata.drop_all(bind=engine)