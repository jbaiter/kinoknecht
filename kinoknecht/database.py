import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import config


logger = logging.getLogger("kinoknecht.database")
dbfile = os.path.abspath(config.db_file)
engine = create_engine('sqlite:///' + dbfile, convert_unicode=True)
db_session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    global db_session
    if not db_session:
        db_session = scoped_session(sessionmaker(bind=engine))

    import kinoknecht.models
    Base.metadata.create_all(bind=engine)
    logger.debug('Database successfully set up!')

def shutdown_db():
    db_session.remove()
    Base.metadata.drop_all(bind=engine)

