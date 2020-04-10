# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import sys

from pulseguardian import config, management as pulse_management
from pulseguardian.model.base import db_session, init_db
from pulseguardian.model.binding import Binding
from pulseguardian.model.user import User
from pulseguardian.model.pulse_user import RabbitMQAccount
from pulseguardian.model.queue import Queue

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def init_and_clear_db():
    # Initialize the database schema.
    init_db()

    # Remove all users and pulse users created by the web app.
    for rabbitmq_account in RabbitMQAccount.query.all():
        try:
            pulse_management.delete_user(rabbitmq_account.username)
        except pulse_management.PulseManagementException:
            pass

    # Clear the database of old data.
    for queue in Queue.query.all():
        db_session.delete(queue)
    for binding in Binding.query.all():
        db_session.delete(binding)
    for rabbitmq_account in RabbitMQAccount.query.all():
        db_session.delete(rabbitmq_account)
    for user in User.query.all():
        db_session.delete(user)

    db_session.commit()

    logger.info('Finished initializing database.')


def dummy_data():
    # Dummy test users
    User.new_user(email='dummy0@dummy.com')
    users = User.query.all()

    for i in range(4):
        RabbitMQAccount.new_user(
            username='dummy{0}'.format(i),
            password='dummy',
            owners=users[0])

    rabbitmq_accounts = RabbitMQAccount.query.all()

    # And some dummy queues
    dummy_queue = Queue(name='dummy-empty-queue', size=0, owner=rabbitmq_accounts[0])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-non-empty-queue', size=config.warn_queue_size/5, owner=rabbitmq_accounts[0])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-warning-queue', size=config.warn_queue_size + 1, owner=rabbitmq_accounts[1])
    db_session.add(dummy_queue)
    db_session.commit()

    dummy_queue = Queue(name='dummy-deletion-queue', size=int(config.del_queue_size * 1.2), owner=rabbitmq_accounts[2])
    db_session.add(dummy_queue)
    db_session.commit()

    # Test admin user
    User.new_user(email='admin@admin.com', admin=True)

    logger.info('Finished generating dummy data.')


if __name__ == '__main__':
    init_and_clear_db()
    if '--dummy' in sys.argv:
        dummy_data()
