# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import multiprocessing
import os
import socket
import sys
import time
import unittest
import uuid
from urlparse import urlparse

from mozillapulse import consumers, publishers
from mozillapulse.messages.test import TestMessage

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(parent_dir, 'pulseguardian'))

import config
# Changing the DB for the tests before the model is initialized
config.sqlalchemy_engine_url = 'sqlite:///pulseguardian_test.db'

import dbinit
from guardian import PulseGuardian
from management import PulseManagementAPI
from model.user import User
from model.pulse_user import PulseUser
from model.queue import Queue
from model.base import db_session

from docker_setup import (
    create_image, setup_container, teardown_container, check_rabbitmq
)

# Default RabbitMQ host settings
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_MANAGEMENT_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'

DEFAULT_USE_LOCAL = False
DEFAULT_RABBITMQ_TIMEOUT = 20  # in seconds

CONSUMER_USER = 'guardtest'
CONSUMER_PASSWORD = 'guardtest'
CONSUMER_EMAIL = 'guardtest@guardtest.com'

TEST_WARN_SIZE = 20
TEST_DELETE_SIZE = 30
DEFAULT_LOGLEVEL = 'INFO'

# Global pulse configuration.
pulse_cfg = dict(ssl=False)


class AbnormalQueueConsumer(consumers.PulseTestConsumer):

    QUEUE_NAME = 'abnormal.queue'

    @property
    def queue_name(self):
        return self.QUEUE_NAME


class ConsumerSubprocess(multiprocessing.Process):

    def __init__(self, consumer_class, config, durable=False):
        multiprocessing.Process.__init__(self)
        self.consumer_class = consumer_class
        self.config = config
        self.durable = durable
        self.queue = multiprocessing.Queue()

    def run(self):
        queue = self.queue

        def cb(body, message):
            queue.put(body)
            message.ack()
        consumer = self.consumer_class(durable=self.durable, **self.config)
        consumer.configure(topic='#', callback=cb)
        consumer.listen()


class GuardianTest(unittest.TestCase):

    """Launches a consumer process that creates a queue then disconnects,
    and then floods the exchange with messages and checks that PulseGuardian
    warns the queue's owner and deletes the queue if it gets over the maximum
    size.
    """

    # Defaults; can be overridden for particular tests.
    consumer_class = consumers.PulseTestConsumer
    publisher_class = publishers.PulseTestPublisher

    proc = None
    QUEUE_CHECK_PERIOD = 0.05
    QUEUE_CHECK_ATTEMPTS = 4000
    QUEUE_RECORD_CHECK_PERIOD = 0.1
    QUEUE_RECORD_CHECK_ATTEMPTS = 50
    PUBLISHER_CONNECT_ATTEMPTS = 50

    def setUp(self):
        global pulse_cfg

        self.proc = None
        self.publisher = None
        self.management_api = PulseManagementAPI(
            host=pulse_cfg['host'],
            user=pulse_cfg['user'],
            management_port=pulse_cfg['management_port'],
            password=pulse_cfg['password'])
        self.guardian = PulseGuardian(self.management_api,
                                      warn_queue_size=TEST_WARN_SIZE,
                                      del_queue_size=TEST_DELETE_SIZE,
                                      emails=False)

        # Hack in a test config.
        dbinit.pulse_management = self.management_api
        dbinit.init_and_clear_db()

        self.consumer_cfg = pulse_cfg.copy()
        self.consumer_cfg['applabel'] = str(uuid.uuid1())
        # Configure/create the test user to be used for message consumption.
        self.consumer_cfg['user'] = CONSUMER_USER
        self.consumer_cfg['password'] = CONSUMER_PASSWORD

        self.user = User.new_user(email=CONSUMER_EMAIL, admin=False)

        db_session.add(self.user)
        db_session.commit()

        self.pulse_user = PulseUser.new_user(
            username=CONSUMER_USER,
            password=CONSUMER_PASSWORD,
            owner=self.user,
            management_api=self.management_api)

        db_session.add(self.pulse_user)
        db_session.commit()

    def tearDown(self):
        self._terminate_consumer_proc()  # Just in case.
        for queue in Queue.query.all():
            self.management_api.delete_queue(vhost=DEFAULT_RABBIT_VHOST,
                                             queue=queue.name)

    def _build_message(self, msg_id):
        msg = TestMessage()
        msg.set_data('id', msg_id)
        return msg

    def _create_publisher(self, create_exchange=True):
        self.publisher = self.publisher_class(**pulse_cfg)

        if create_exchange:
            attempts = 0
            exc = None

            while attempts < self.PUBLISHER_CONNECT_ATTEMPTS:
                attempts += 1
                if attempts > 1:
                    time.sleep(0.1)

                try:
                    self.publisher.publish(self._build_message(0))
                except socket.error as e:
                    exc = e
                else:
                    exc = None
                    break

            if exc:
                raise exc

    def _create_consumer_proc(self, durable=False):
        self.proc = ConsumerSubprocess(self.consumer_class, self.consumer_cfg,
                                       durable)
        self.proc.start()

    def _terminate_consumer_proc(self):
        if self.proc:
            self.proc.terminate()
            self.proc.join()
            self.proc = None

    def _wait_for_queue(self, queue_should_exist=True):
        # Wait until queue has been created by consumer process.
        consumer = self.consumer_class(**self.consumer_cfg)
        consumer.configure(topic='#', callback=lambda x, y: None)
        attempts = 0
        while attempts < self.QUEUE_CHECK_ATTEMPTS:
            attempts += 1
            if attempts > 1:
                time.sleep(self.QUEUE_CHECK_PERIOD)
            if consumer.queue_exists() == queue_should_exist:
                break
        self.assertEqual(consumer.queue_exists(), queue_should_exist)

    def _wait_for_queue_record(self):
        '''Wait until one or more queues have been added to the database.'''
        attempts = 0
        while attempts < self.QUEUE_RECORD_CHECK_ATTEMPTS:
            attempts += 1
            if attempts > 1:
                time.sleep(self.QUEUE_RECORD_CHECK_PERIOD)
            self.guardian.monitor_queues(self.management_api.queues())
            if Queue.query.first():
                break

    def test_abnormal_queue_name(self):
        self.consumer_class = AbnormalQueueConsumer
        # Use account with full permissions.
        self.consumer_cfg['user'] = pulse_cfg['user']
        self.consumer_cfg['password'] = pulse_cfg['password']

        self._create_publisher()
        self._create_consumer_proc()
        self._wait_for_queue()
        self._wait_for_queue_record()

        queue = Queue.query.filter(Queue.name ==
                                   AbnormalQueueConsumer.QUEUE_NAME).first()
        owner = queue.owner

        # Queue is not durable and will be cleaned up when consumer process
        # exits; delete it from the queue to avoid assertion failure in
        # tearDown().
        self._terminate_consumer_proc()
        self._wait_for_queue(False)
        db_session.delete(queue)
        db_session.commit()

        self.assertEqual(owner, None)

    def test_warning(self):
        self._create_publisher()
        self._create_consumer_proc(durable=True)
        self._wait_for_queue()
        self._wait_for_queue_record()
        self._terminate_consumer_proc()

        # Queue should still exist.
        self._wait_for_queue()

        # Get the queue's object.
        db_session.refresh(self.pulse_user)

        # Queue multiple messages while no consumer exists.
        for i in xrange(self.guardian.warn_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait for messages to be taken into account and get the warned
        # messages, if any.
        for i in xrange(10):
            time.sleep(0.3)
            queues_to_warn = set(q_data['name'] for q_data
                                 in self.management_api.queues()
                                 if self.guardian.warn_queue_size
                                 < q_data['messages_ready']
                                 <= self.guardian.del_queue_size)
            if queues_to_warn:
                break

        # Test that no queue has been warned at the beginning of the process.
        self.assertTrue(not any(q.warned for q in self.pulse_user.queues))
        # ... but some queues should be now.
        self.assertTrue(len(queues_to_warn) > 0)

        # Monitor the queues; this should detect queues that should be warned.
        self.guardian.monitor_queues(self.management_api.queues())

        # Refresh the user's queues state.
        db_session.refresh(self.pulse_user)

        # Test that the queues that had to be "warned" were.
        self.assertTrue(all(q.warned for q in self.pulse_user.queues
                            if q in queues_to_warn))

        # The queues that needed to be warned haven't been deleted.
        queues_to_warn_bis = set(q_data['name'] for q_data
                                 in self.management_api.queues()
                                 if self.guardian.warn_queue_size
                                    < q_data['messages_ready']
                                    <= self.guardian.del_queue_size)
        self.assertEqual(queues_to_warn_bis, queues_to_warn)

    def test_delete(self):
        self._create_publisher()
        self._create_consumer_proc(durable=True)
        self._wait_for_queue()
        self._wait_for_queue_record()
        self._terminate_consumer_proc()

        # Queue should still exist.
        self._wait_for_queue()

        # Get the queue's object
        db_session.refresh(self.pulse_user)

        self.assertTrue(len(self.pulse_user.queues) > 0)

        # Queue multiple messages while no consumer exists.
        for i in xrange(self.guardian.del_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait some time for published messages to be taken into account.
        for i in xrange(10):
            time.sleep(0.3)
            queues_to_delete = [q_data['name'] for q_data
                                in self.management_api.queues()
                                if q_data['messages_ready']
                                   > self.guardian.del_queue_size]
            if queues_to_delete:
                break

        # Test that there are some queues that should be deleted.
        self.assertTrue(len(queues_to_delete) > 0)

        # Setting up a callback to capture deleted queues
        deleted_queues = []
        def on_delete(queue):
            deleted_queues.append(queue)
        self.guardian.on_delete = on_delete

        # Monitor the queues; this should create the queue object and assign
        # it to the user.
        for i in xrange(20):
            self.guardian.monitor_queues(self.management_api.queues())
            time.sleep(0.2)

        # Test that the queues that had to be deleted were deleted...
        self.assertTrue(not any(q in queues_to_delete for q
                                in self.management_api.queues()))
        # And that they were deleted by guardian...
        self.assertEqual(sorted(queues_to_delete), sorted(deleted_queues))
        # And that no queue has overgrown.
        queues_to_delete = [q_data['name'] for q_data
                            in self.management_api.queues()
                            if q_data['messages_ready'] >
                               self.guardian.del_queue_size]
        self.assertTrue(len(queues_to_delete) == 0)


class ModelTest(unittest.TestCase):

    """Tests the underlying model (users and queues)."""

    def setUp(self):
        dbinit.init_and_clear_db()

    def test_user(self):
        user = User.new_user(email='dUmMy@EmAil.com', admin=False)
        db_session.add(user)
        db_session.commit()

        pulse_user = PulseUser.new_user(username='dummy',
                                        password='DummyPassword',
                                        owner=user,
                                        management_api=None)
        db_session.add(pulse_user)
        db_session.commit()

        self.assertTrue(user in User.query.all())

        # Emails are normalized by putting them lower-case
        self.assertEqual(
            User.query.filter(User.email == 'dummy@email.com').first(), user)
        self.assertEqual(
            PulseUser.query.filter(PulseUser.username == 'dummy').first(),
            pulse_user)
        self.assertEqual(
            PulseUser.query.filter(PulseUser.username == 'DUMMY').first(),
            None)


def setup_host():
    global pulse_cfg

    if pulse_cfg['host'] != DEFAULT_RABBIT_HOST:
        # Not equal to default: use the supplied host
        return
    else:
        try:
            # IF DOCKER_HOST env variable exists, use as the host value
            host = os.environ['DOCKER_HOST']

            # Value of env variable will be something similar to:
            # 'tcp://192.168.59.103:2376'. We only need the ip
            pulse_cfg['host'] = urlparse(host).hostname
        except KeyError:
            # Env variable doesn't exist, use default
            pass
        finally:
            pulse_cfg['port'] = 5673
            pulse_cfg['management_port'] = 15673


def main(pulse_opts):
    global pulse_cfg

    # Configuring logging
    loglevel = pulse_opts['loglevel']
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.disable(level=numeric_level - 1)

    pulse_cfg.update(pulse_opts)

    if not pulse_cfg['use_local']:
        try:
            setup_host()

            # Create image and container.
            # If the image already exists, it will use that one.
            create_image()
            setup_container()

            # Although the container has started, the rabbitmq-server needs
            # some time to start.
            logging.info('Waiting for rabbitmq-server to start.')
            timeout = time.time() + DEFAULT_RABBITMQ_TIMEOUT
            while True:
                # Check if rabbitmq-server has started
                if check_rabbitmq():
                    break

                # Timeout exceeded
                if time.time() > timeout:
                    raise RuntimeError('rabbitmq-server startup timeout '
                                       'exceeded')

                # We don't want to hog the CPU, so we sleep 1 second before
                # trying again.
                time.sleep(1)

            # rabbitmq-server is already running, we can run our tests
            unittest.main(argv=sys.argv[0:1])
        finally:
            teardown_container()
    else:
        unittest.main(argv=sys.argv[0:1])


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('--host', action='store', dest='host',
                      default=DEFAULT_RABBIT_HOST,
                      help='host running RabbitMQ; defaults to %s' %
                      DEFAULT_RABBIT_HOST)
    parser.add_option('--port', action='store', type='int', dest='port',
                      default=DEFAULT_RABBIT_PORT,
                      help='port on which RabbitMQ is running; defaults to %d'
                      % DEFAULT_RABBIT_PORT)
    parser.add_option('--management-port', action='store', type='int',
                      dest='management_port',
                      default=DEFAULT_RABBIT_MANAGEMENT_PORT,
                      help='RabbitMQ managment port; defaults to %d'
                      % DEFAULT_RABBIT_MANAGEMENT_PORT)
    parser.add_option('--vhost', action='store', dest='vhost',
                      default=DEFAULT_RABBIT_VHOST,
                      help='name of pulse vhost; defaults to "%s"' %
                      DEFAULT_RABBIT_VHOST)
    parser.add_option('--user', action='store', dest='user',
                      default=DEFAULT_RABBIT_USER,
                      help='name of pulse RabbitMQ user; defaults to "%s"' %
                      DEFAULT_RABBIT_USER)
    parser.add_option('--password', action='store', dest='password',
                      default=DEFAULT_RABBIT_PASSWORD,
                      help='password of pulse RabbitMQ user; defaults to "%s"'
                      % DEFAULT_RABBIT_PASSWORD)
    parser.add_option('--use-local', action='store_true', dest='use_local',
                      default=DEFAULT_USE_LOCAL,
                      help='use local setup; defaults to "%s"'
                      % DEFAULT_USE_LOCAL)
    parser.add_option('--log', action='store', dest='loglevel',
                      default=DEFAULT_LOGLEVEL,
                      help='logging level; defaults to "%s"'
                      % DEFAULT_LOGLEVEL)
    (opts, args) = parser.parse_args()
    main(opts.__dict__)
