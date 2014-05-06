import sys
sys.path.append('..')

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import config
engine = create_engine(config.sqlalchemy_engine_url, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db(engine=engine):
    Base.metadata.create_all(bind=engine)

def assign_test_db(test_engine_url='sqlite:///test.db'):
    global db_session

    # Creating engine and session
    test_engine = create_engine(test_engine_url, convert_unicode=True)
    test_db_session = scoped_session(sessionmaker(autocommit=False,
                                                  autoflush=False,
                                                  bind=test_engine))
  
    # Re-binding with the Base model
    Base.query = test_db_session.query_property()
    Base.metadata.create_all(bind=test_engine)

    db_session = test_db_session
    return test_db_session