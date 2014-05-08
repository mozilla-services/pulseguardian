import sys
import logging

from model.base import db_session, init_db
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException
import config

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

pulse_management = PulseManagementAPI(host=config.rabbit_host, user=config.rabbit_user, password=config.rabbit_password)

def init_and_clear_db():
    # Initializing the database schema
    init_db()

    # Removing all pulse users created by the web app
    for user in User.query.all():
        try:
            pulse_management.delete_user(user.username)
        except PulseManagementException:
            pass

    # Clearing the database from old data
    Queue.query.delete()
    User.query.delete()

    logger.info('Finished initializing database')


def dummy_data():
    # Dummy test users
    for i in xrange(4):
        dummy_user = User.new_user(
            email='dummy{}@dummy.com'.format(i), username='dummy{}'.format(i),
            password='dummy')
        dummy_user.activate(pulse_management)
        db_session.add(dummy_user)
    db_session.commit()

    users = User.query.all()

    # And some dummy queues
    dummy_queue = Queue(name='dummy-empty-queue', size=0, owner=users[0])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-non-empty-queue', size=config.warn_queue_size/5, owner=users[0])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-warning-queue', size=config.warn_queue_size + 1, owner=users[1])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-deletion-queue', size=int(config.del_queue_size * 1.2), owner=users[2])
    db_session.add(dummy_queue)
    db_session.commit()


    # Test admin user
    admin = User.new_user(
        email='admin@admin.com', username='admin', password='admin', admin=True)
    admin.activate(pulse_management)
    db_session.add(admin)
    db_session.commit()

    logger.info('Finished generating dummy data')

if __name__ == '__main__':
    init_and_clear_db()
    if '--dummy' in sys.argv:
        dummy_data()
