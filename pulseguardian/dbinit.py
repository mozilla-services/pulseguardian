# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import sys

import config

from model.base import db_session, init_db
from model.user import User
from model.pulse_user import PulseUser
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

pulse_management = PulseManagementAPI(host=config.rabbit_host,
                                      user=config.rabbit_user,
                                      password=config.rabbit_password)


def init_and_clear_db():
    # Initialize the database schema.
    init_db()

    # Remove all users and pulse users created by the web app.
    for pulse_user in PulseUser.query.all():
        try:
            pulse_management.delete_user(pulse_user.username)
        except PulseManagementException:
            pass

    # Clear the database of old data.
    for queue in Queue.query.all():
        db_session.delete(queue)
    for pulse_user in PulseUser.query.all():
        db_session.delete(pulse_user)
    for user in User.query.all():
        db_session.delete(user)

    db_session.commit()

    logger.info('Finished initializing database.')


def dummy_data():
    # Dummy test users
    for i in xrange(4):
        User.new_user(
            email='dummy{0}@dummy.com'.format(i), username='dummy{0}'.format(i),
            password='dummy', management_api=pulse_management)

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
    User.new_user(
        email='admin@admin.com', username='dummy-admin', password='dummy-admin',
        management_api=pulse_management, admin=True)

    logger.info('Finished generating dummy data.')

if __name__ == '__main__':
    init_and_clear_db()
    if '--dummy' in sys.argv:
        dummy_data()
