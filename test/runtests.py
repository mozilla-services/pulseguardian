# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import logging
import multiprocessing
import os
import socket
import sys
import time
import unittest
import uuid
from urllib.parse import urlparse

from kombu import Exchange
from mozillapulse import consumers, publishers
from mozillapulse.messages.test import TestMessage

os.environ['FLASK_SECRET_KEY'] = base64.b64encode(os.urandom(24)).decode('ascii')

from pulseguardian import config

# Change the DB for the tests and set fake_account *before* the model is initialized.
config.database_url = 'sqlite:///pulseguardian_test.db'
config.fake_account = 'guardtest@guardtest.com'

from docker_setup import (check_rabbitmq, create_image,
                          setup_container, teardown_container)

from pulseguardian import dbinit, management as pulse_management, web
from pulseguardian.guardian import PulseGuardian
from pulseguardian.model.base import db_session
from pulseguardian.model.binding import Binding
from pulseguardian.model.pulse_user import RabbitMQAccount
from pulseguardian.model.queue import Queue
from pulseguardian.model.user import User

web.app.config['TESTING'] = True

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
ADMIN_EMAIL = 'admin@guardtest.com'

TEST_WARN_SIZE = 20
TEST_DELETE_SIZE = 30
DEFAULT_LOGLEVEL = 'INFO'

# Global pulse configuration.
pulse_cfg = dict(ssl=False)


class PulseGuardianTestConsumer(consumers.PulseTestConsumer):

    QUEUE_NAME = None

    @property
    def queue_name(self):
        return self.QUEUE_NAME


class AbnormalQueueConsumer(PulseGuardianTestConsumer):

    QUEUE_NAME = 'abnormal.queue'


class ReservedQueueConsumer(PulseGuardianTestConsumer):

    QUEUE_NAME = 'queue/reserved-user/abc'


class SecondaryQueueConsumer(PulseGuardianTestConsumer):

    def __init__(self, **kwargs):
        super(SecondaryQueueConsumer, self).__init__(**kwargs)
        self.QUEUE_NAME = 'queue/{}/secondary'.format(
            CONSUMER_USER)


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
        self.guardian = PulseGuardian(warn_queue_size=TEST_WARN_SIZE,
                                      del_queue_size=TEST_DELETE_SIZE,
                                      emails=False)

        dbinit.init_and_clear_db()

        self.consumer_cfg = pulse_cfg.copy()
        self.consumer_cfg['applabel'] = str(uuid.uuid1())
        # Configure/create the test user to be used for message consumption.
        self.consumer_cfg['user'] = CONSUMER_USER
        self.consumer_cfg['password'] = CONSUMER_PASSWORD

        self.user = User.new_user(email=CONSUMER_EMAIL, admin=False)
        # As a default owner for rabbitmq_account in some tests where an owner
        # is not provided.
        self.admin = User.new_user(email=ADMIN_EMAIL, admin=True)

        db_session.add(self.user)
        db_session.commit()

        self.rabbitmq_account = RabbitMQAccount.new_user(
            username=CONSUMER_USER,
            password=CONSUMER_PASSWORD,
            owners=self.user)

        db_session.add(self.rabbitmq_account)
        db_session.commit()

    def tearDown(self):
        self._terminate_consumer_proc()  # Just in case.
        for queue in Queue.query.all():
            pulse_management.delete_queue(vhost=DEFAULT_RABBIT_VHOST,
                                          queue=queue.name)

    def _setup_queue(self):
        """Setup a publisher, consumer and Queue, then terminate consumer"""
        self._create_publisher()
        self._create_consumer_proc(durable=True)
        self._wait_for_queue()
        self._wait_for_queue_record()
        self._terminate_consumer_proc()

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

    def _create_passive_consumer(self):
        cfg = self.consumer_cfg.copy()
        cfg['connect'] = False
        consumer = self.consumer_class(**self.consumer_cfg)
        consumer.configure(topic='#', callback=lambda x, y: None)
        return consumer

    def _wait_for_queue(self, queue_should_exist=True):
        '''Wait until queue has been created by consumer process.'''
        consumer = self._create_passive_consumer()
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
        consumer = self._create_passive_consumer()
        attempts = 0
        while attempts < self.QUEUE_RECORD_CHECK_ATTEMPTS:
            attempts += 1
            if attempts > 1:
                time.sleep(self.QUEUE_RECORD_CHECK_PERIOD)
            self.guardian.monitor_queues(pulse_management.queues(vhost='/'),
                                         pulse_management.bindings(vhost='/'))
            if Queue.query.filter(Queue.name == consumer.queue_name).first():
                break

    def _wait_for_binding_record(self, queue_name, exchange_name, routing_key):
        """Wait until a binding has been added to the database"""
        consumer = self._create_passive_consumer()
        attempts = 0
        while attempts < self.QUEUE_RECORD_CHECK_ATTEMPTS:
            attempts += 1
            if attempts > 1:
                time.sleep(self.QUEUE_RECORD_CHECK_PERIOD)
            self.guardian.monitor_queues(pulse_management.queues(vhost='/'),
                                         pulse_management.bindings(vhost='/'))
            if Binding.query.filter(
                                    Binding.queue_name == queue_name,
                                    Binding.exchange == exchange_name,
                                    Binding.routing_key == routing_key).first():
                break

    def _wait_for_binding_delete(self, queue_name, exchange_name, routing_key):
        """Wait until a binding has been removed from the database"""
        consumer = self._create_passive_consumer()
        attempts = 0
        while attempts < self.QUEUE_RECORD_CHECK_ATTEMPTS:
            attempts += 1
            if attempts > 1:
                time.sleep(self.QUEUE_RECORD_CHECK_PERIOD)
            self.guardian.clear_deleted_queues(pulse_management.queues(vhost='/'),
                                               pulse_management.bindings(vhost='/'))
            if not Binding.query.filter(
                                        Binding.queue_name == queue_name,
                                        Binding.exchange == exchange_name,
                                        Binding.routing_key == routing_key).first():
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

    def test_reserved_queue_name(self):
        self.consumer_class = ReservedQueueConsumer
        # Use account with full permissions.
        self.consumer_cfg['user'] = pulse_cfg['user']
        self.consumer_cfg['password'] = pulse_cfg['password']

        config.reserved_users_regex = 'reserved-.*'
        try:
            self._create_publisher()
            self._create_consumer_proc()
            self._wait_for_queue()
            self._wait_for_queue_record()
        finally:
            config.reserved_users_regex = None

        queue = Queue.query.filter(Queue.name ==
                                   ReservedQueueConsumer.QUEUE_NAME).first()

        # Queue is not durable and will be cleaned up when consumer process
        # exits; delete it from the queue to avoid assertion failure in
        # tearDown().
        self._terminate_consumer_proc()
        self._wait_for_queue(False)

        self.assertEqual(queue, None)

    def test_warning(self):
        self._setup_queue()

        # Queue should still exist.
        self._wait_for_queue()

        # Get the queue's object.
        db_session.refresh(self.rabbitmq_account)

        # Queue multiple messages while no consumer exists.
        for i in range(self.guardian.warn_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait for messages to be taken into account and get the warned
        # messages, if any.
        for i in range(100):
            time.sleep(0.3)
            queues_to_warn = set(q_data['name'] for q_data
                                 in pulse_management.queues()
                                 if self.guardian.warn_queue_size
                                 < q_data['messages_ready']
                                 <= self.guardian.del_queue_size)
            if queues_to_warn:
                break

        # Test that no queue has been warned at the beginning of the process.
        self.assertTrue(not any(q.warned for q in self.rabbitmq_account.queues))
        # ... but some queues should be now.
        self.assertGreater(len(queues_to_warn), 0)

        # Monitor the queues; this should detect queues that should be warned.
        self.guardian.monitor_queues(pulse_management.queues(vhost='/'),
                                     pulse_management.bindings(vhost='/'))

        # Refresh the user's queues state.
        db_session.refresh(self.rabbitmq_account)

        # Test that the queues that had to be "warned" were.
        self.assertTrue(all(q.warned for q in self.rabbitmq_account.queues
                            if q in queues_to_warn))

        # The queues that needed to be warned haven't been deleted.
        queues_to_warn_bis = set(q_data['name'] for q_data
                                 in pulse_management.queues()
                                 if self.guardian.warn_queue_size
                                 < q_data['messages_ready']
                                 <= self.guardian.del_queue_size)
        self.assertEqual(queues_to_warn_bis, queues_to_warn)

    def test_delete(self):
        self._setup_queue()

        # Queue should still exist.
        self._wait_for_queue()

        # Get the queue's object
        db_session.refresh(self.rabbitmq_account)

        self.assertGreater(len(self.rabbitmq_account.queues), 0)

        # Queue multiple messages while no consumer exists.
        for i in range(self.guardian.del_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait some time for published messages to be taken into account.
        for i in range(100):
            time.sleep(0.3)
            queues_to_delete = [q_data['name'] for q_data
                                in pulse_management.queues()
                                if q_data['messages_ready']
                                > self.guardian.del_queue_size]
            if queues_to_delete:
                break

        # Test that there are some queues that should be deleted.
        self.assertGreater(len(queues_to_delete), 0)

        # Setting up a callback to capture deleted queues
        deleted_queues = []

        def on_delete(queue):
            deleted_queues.append(queue)

        self.guardian.on_delete = on_delete

        # Monitor the queues; this should delete overgrown queues
        self.guardian.monitor_queues(pulse_management.queues(vhost='/'),
                                     pulse_management.bindings(vhost='/'))

        # Test that the queues that had to be deleted were deleted...
        self.assertTrue(not any(q in queues_to_delete for q
                                in pulse_management.queues()))
        # And that they were deleted by guardian...
        self.assertEqual(sorted(queues_to_delete), sorted(deleted_queues))
        # And that no queue has overgrown.
        queues_to_delete = [q_data['name'] for q_data
                            in pulse_management.queues()
                            if q_data['messages_ready']
                            > self.guardian.del_queue_size]
        self.assertEqual(len(queues_to_delete), 0)

    def test_delete_skip_unbounded(self):
        self._setup_queue()

        # Queue should still exist.
        self._wait_for_queue()

        # Get the queue's object
        db_session.refresh(self.rabbitmq_account)

        self.assertGreater(len(self.rabbitmq_account.queues), 0)

        # set queues as unbound so they won't be deleted
        for queue in self.rabbitmq_account.queues:
            queue.unbound = 1

        # Queue multiple messages while no consumer exists.
        for i in range(self.guardian.del_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait some time for published messages to be taken into account.
        for i in range(100):
            time.sleep(0.3)
            queues_to_delete = [q_data['name'] for q_data
                                in pulse_management.queues()
                                if q_data['messages_ready']
                                > self.guardian.del_queue_size]
            if queues_to_delete:
                break

        # Test that there are some queues that should be deleted.
        self.assertGreater(len(queues_to_delete), 0)

        # Setting up a callback to capture deleted queues
        deleted_queues = []

        def on_delete(queue):
            deleted_queues.append(queue)
        self.guardian.on_delete = on_delete

        # Run through the code that decides whether to delete a queue
        # that has grown too large.
        # In this case, it should run the check and decide to not delete
        # any queues.
        self.guardian.monitor_queues(pulse_management.queues(vhost='/'),
                                     pulse_management.bindings(vhost='/'))

        # Test that none of the queues were deleted...
        self.assertTrue(all(q in queues_to_delete for q
                            in pulse_management.queues()))

        # And that they were not deleted by guardian...
        self.assertGreater(len(queues_to_delete), 0)

    def test_binding(self):
        """Test that you can get the bindings for a queue"""
        self._setup_queue()

        # Get the queue's object
        db_session.refresh(self.rabbitmq_account)

        self.assertEqual(len(self.rabbitmq_account.queues), 1)

        # check queue bindings in the DB
        queues = Queue.query.all()
        self.assertEqual(len(queues), 1)
        queue = queues[0]
        bindings = queue.bindings
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].routing_key, "#")
        self.assertEqual(bindings[0].exchange, "exchange/pulse/test")

    def test_create_binding_different_queue_same_exchange_routing_key(self):
        """
        Test create bindings for two queues with same exchange and routing key
        """
        self.consumer_class = consumers.PulseTestConsumer
        self._setup_queue()

        # create a second queue with the same binding
        self.consumer_class = SecondaryQueueConsumer
        self._setup_queue()

        # check queue bindings in the DB
        queues = Queue.query.all()
        self.assertEqual(len(queues), 2)
        for queue in queues:
            bindings = queue.bindings
            self.assertEqual(len(bindings), 1)
            self.assertEqual(bindings[0].routing_key, "#")
            self.assertEqual(bindings[0].exchange, "exchange/pulse/test")

    def test_add_delete_binding(self):
        """Test adding and removing a binding from a queue"""
        self._setup_queue()

        consumer = self._create_passive_consumer()
        exchange = Exchange(consumer.exchange, type='topic')
        queue = consumer._create_queue(exchange)
        bound = queue.bind(consumer.connection.channel())
        routing_key = "foo"
        bound.bind_to(exchange=consumer.exchange, routing_key=routing_key)

        self._wait_for_binding_record(queue.name, exchange.name, routing_key)

        def test_bindings(exp_routing_keys):
            queues = Queue.query.all()
            self.assertEqual(len(queues), 1)
            self.assertEqual(len(queues[0].bindings), len(exp_routing_keys))
            db_queue = queues[0]

            mgmt_bindings = pulse_management.queue_bindings('/', db_queue.name)
            mgmt_routing_keys = {x["routing_key"] for x in mgmt_bindings}
            self.assertEqual(mgmt_routing_keys, exp_routing_keys)

            db_routing_keys = {x.routing_key for x in db_queue.bindings}
            self.assertEqual(db_routing_keys, exp_routing_keys)

        test_bindings({"#", "foo"})

        # test deleting one of the bindings
        bound.unbind_from(exchange=exchange, routing_key=routing_key)
        self._wait_for_binding_delete(queue.name, exchange.name, routing_key)

        test_bindings({"#"})


class ModelTest(unittest.TestCase):

    """Tests the underlying model (users and queues)."""

    def setUp(self):
        dbinit.init_and_clear_db()

    def test_user(self):
        user = User.new_user(email='dUmMy@EmAil.com', admin=False)
        db_session.add(user)
        db_session.commit()

        rabbitmq_account = RabbitMQAccount.new_user(username='dummy',
                                                    password='DummyPassword',
                                                    owners=user,
                                                    create_rabbitmq_user=False)
        db_session.add(rabbitmq_account)
        db_session.commit()

        self.assertTrue(user in User.query.all())

        # Emails are normalized by putting them lower-case
        self.assertEqual(
            User.query.filter(User.email == 'dummy@email.com').first(), user)
        self.assertEqual(
            RabbitMQAccount.query.filter(
                RabbitMQAccount.username == 'dummy').first(),
            rabbitmq_account)
        self.assertEqual(
            RabbitMQAccount.query.filter(
                RabbitMQAccount.username == 'DUMMY').first(),
            None)

    def test_user_set_admin(self):
        user = User.new_user(email='adminusr@email.com', admin=False)
        db_session.add(user)
        db_session.commit()

        user = User.query.filter(User.email == 'adminusr@email.com').first()
        user.set_admin(True)

        userDb = User.query.filter(User.email == 'adminusr@email.com').first()

        self.assertTrue(userDb.admin)


class WebTest(unittest.TestCase):

    def setUp(self):
        dbinit.init_and_clear_db()

    def setup_3_users(self):
        mif = "mif@maf.baz"
        maf = "foo@bar.baz"
        self.curr_email = CONSUMER_EMAIL
        self.all_emails = [mif, maf, self.curr_email]

        mif_u = User.new_user(email=mif, admin=False)
        maf_u = User.new_user(email=maf, admin=False)
        self.curr_user = User.new_user(email=self.curr_email, admin=False)
        self.all_users = [mif_u, maf_u, self.curr_user]

    def set_rabbitmq_account_email_list(self, username, email_str):
        with web.app.test_client() as c:
            templates = "{}/pulseguardian/templates".format(os.getcwd())
            c.application.template_folder = templates
            with c.session_transaction() as sess:
                sess['email'] = CONSUMER_EMAIL
                sess['fake_account'] = True
                sess['logged_in'] = True

            c.post('/update_info',
                   data={"owners-list": email_str,
                         "rabbitmq-username": username,
                         "new-password": "",
                         "new-password-verification": ""})

        pu_after = RabbitMQAccount.query.first()
        pu_after_emails = {owner.email for owner in pu_after.owners}
        return pu_after_emails

    def test_rabbitmq_account_single_to_multiple_ownership(self):
        self.setup_3_users()
        RabbitMQAccount.new_user(username="mick",
                                 owners=self.curr_user,
                                 password="mitochondria5")

        new_emails = self.set_rabbitmq_account_email_list(
            "mick", ','.join(self.all_emails))
        self.assertEqual(new_emails, set(self.all_emails))

    def test_rabbitmq_account_multiple_to_single_ownership(self):
        self.setup_3_users()
        RabbitMQAccount.new_user(username="mick",
                                 owners=self.all_users,
                                 password="mitochondria5")

        new_emails = self.set_rabbitmq_account_email_list("mick",
                                                          self.curr_email)
        self.assertEqual(new_emails, {self.curr_email})

    def test_pulse_odd_whitespace_ownership_list(self):
        self.setup_3_users()
        RabbitMQAccount.new_user(username="mick",
                                 owners=self.all_users,
                                 password="mitochondria5")

        new_emails = self.set_rabbitmq_account_email_list(
            "mick", ",  {},   {},{},".format(*self.all_emails))
        self.assertEqual(new_emails, set(self.all_emails))

    def test_register_reserved_name(self):
        try:
            config.reserved_users_regex = 'rese[r]ved'
            config.reserved_users_message = 'NO RESERVED NAMES'
            with web.app.test_client() as c:
                templates = "{}/pulseguardian/templates".format(os.getcwd())
                c.application.template_folder = templates
                with c.session_transaction() as sess:
                    sess['email'] = CONSUMER_EMAIL
                    sess['fake_account'] = True
                    sess['logged_in'] = True

                resp = c.post(
                    '/register', data={
                        "username": "reserved-name",
                        "password": "ohXoof9yoo",
                        "password-verification": "ohXoof9yoo",
                        "owners-list": CONSUMER_EMAIL,
                    })
                self.assertIn(config.reserved_users_message.encode('ascii'), resp.data)
        finally:
            config.reserved_users_regex = None
            config.reserved_users_message = None


def setup_host():
    global pulse_cfg

    if pulse_cfg['host'] == DEFAULT_RABBIT_HOST:
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
            pulse_cfg['port'] = 5672
            pulse_cfg['management_port'] = 15672
    # else, use the supplied host

    # set the rabbit values of the ``config`` based on the pulse_cfg
    config.rabbit_management_url = 'http://{}:{}/api/'.format(
        pulse_cfg['host'], pulse_cfg['management_port'])
    config.rabbit_user = pulse_cfg['user']
    config.rabbit_password = pulse_cfg['password']


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
