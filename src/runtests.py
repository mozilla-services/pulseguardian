# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

import multiprocessing
import time
import unittest
import uuid
import sys

from mozillapulse import consumers, publishers
from mozillapulse.messages.base import GenericMessage

import config
# Changing the DB for the tests before the model is initialized
config.sqlalchemy_engine_url = 'sqlite:///pulseguardian_test.db'

from management import PulseManagementAPI
from guardian import PulseGuardian
from model.user import User
from model.queue import Queue
from model.base import db_session, init_db
from dbinit import init_and_clear_db

# Initializing test DB
init_db()

# Default RabbitMQ host settings
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'

CONSUMER_USER = 'guardtest'
CONSUMER_PASSWORD = 'guardtest'
CONSUMER_EMAIL = 'guardtest@guardtest.com'

# Global pulse configuration.
pulse_cfg = dict()


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
    warns the queue's owner and deletes the queue if it get's over the maximum size
    """

    consumer_class = consumers.PulseTestConsumer
    publisher_class = publishers.PulseTestPublisher

    proc = None
    QUEUE_CHECK_PERIOD = 0.05
    QUEUE_CHECK_ATTEMPTS = 4000

    def _build_message(self, msg_id):
        msg = TestMessage()
        msg.set_data('id', msg_id)
        return msg

    def setUp(self):
        init_and_clear_db()
        self.management_api = PulseManagementAPI()
        self.guardian = PulseGuardian(self.management_api, emails=False)

        self.consumer_cfg = pulse_cfg.copy()
        self.consumer_cfg['applabel'] = str(uuid.uuid1())

        # Configure / Create the test user to be used for message consumption
        self.consumer_cfg['user'], self.consumer_cfg['password'] = CONSUMER_USER, CONSUMER_PASSWORD
        username, password = self.consumer_cfg['user'], self.consumer_cfg['password']
        self.user = User.query.filter(User.username == username).first()
        if self.user is None:
            self.user = User.new_user(username=username, email=CONSUMER_EMAIL, password=password)
            self.user.activate(self.management_api)
            db_session.add(self.user)
            db_session.commit()

        self.publisher = self.publisher_class(**pulse_cfg)

    def tearDown(self):
        self.terminate_proc()
        init_and_clear_db()

    def terminate_proc(self):
        if self.proc:
            self.proc.terminate()
            self.proc.join()
            self.proc = None

    def _wait_for_queue(self, config, queue_should_exist=True):
        # Wait until queue has been created by consumer process.
        consumer = self.consumer_class(**config)
        consumer.configure(topic='#', callback=lambda x, y: None)
        attempts = 0
        while attempts < self.QUEUE_CHECK_ATTEMPTS:
            attempts += 1
            if consumer.queue_exists() == queue_should_exist:
                break
            time.sleep(self.QUEUE_CHECK_PERIOD)
        self.assertEqual(consumer.queue_exists(), queue_should_exist)

    def _get_verify_msg(self, msg):
        try:
            received_data = self.proc.queue.get(timeout=5)
        except Queue.Empty:
            self.fail('did not receive message from consumer process')
        self.assertEqual(msg.routing_key, received_data['_meta']['routing_key'])
        received_payload = {}
        for k, v in received_data['payload'].iteritems():
            received_payload[k.encode('ascii')] = v.encode('ascii')
        self.assertEqual(msg.data, received_payload)

    def test_warning(self):
        self.management_api.delete_all_queues()

        # Publish some messages
        for i in xrange(10):
            msg = self._build_message(0)
            self.publisher.publish(msg)

        # Start the consumer
        self.proc = ConsumerSubprocess(self.consumer_class, self.consumer_cfg, True)
        self.proc.start()
        self._wait_for_queue(self.consumer_cfg)

        # Monitor the queues, this should create the queue object and assign it to the user
        for i in xrange(10):
            self.guardian.monitor_queues(self.management_api.queues())
            time.sleep(0.2)

        # Terminate the consumer process
        self.terminate_proc()

        # Queue should still exist.
        self._wait_for_queue(self.consumer_cfg)

        # Get the queue's object
        db_session.refresh(self.user)

        # Queue multiple messages while no consumer exists.
        for i in xrange(config.warn_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait for messages to be taken into account and get the warned messages if any
        for i in xrange(10):
            time.sleep(0.3)
            queues_to_warn = {q_data['name'] for q_data in self.management_api.queues()
                              if config.warn_queue_size < q_data['messages_ready'] <= config.del_queue_size}
            if queues_to_warn:
                break

        # Test that no queue have been warned at the beginning of the process
        self.assertTrue(not any(q.warned for q in self.user.queues))
        # ... but some queues should be
        self.assertGreater(len(queues_to_warn), 0)

        # Monitor the queues, this should detect queues that should be warned
        self.guardian.monitor_queues(self.management_api.queues())

        # Refreshing the user's queues state
        db_session.refresh(self.user)

        # Test that the queues that had to be "warned" were
        self.assertTrue(all(q.warned for q in self.user.queues if q in queues_to_warn))
        # The queues that needed to be warned haven't been deleted
        queues_to_warn_bis = {q_data['name'] for q_data in self.management_api.queues()
                              if config.warn_queue_size < q_data['messages_ready'] <= config.del_queue_size}
        self.assertEqual(queues_to_warn_bis, queues_to_warn)

        # Reinitialize the db
        init_and_clear_db()


    def test_delete(self):
        self.management_api.delete_all_queues()

        # Publish some messages
        for i in xrange(10):
            msg = self._build_message(0)
            self.publisher.publish(msg)

        # Start the consumer
        self.proc = ConsumerSubprocess(self.consumer_class, self.consumer_cfg, True)
        self.proc.start()
        self._wait_for_queue(self.consumer_cfg)

        # Monitor the queues, this should create the queue object and assign it to the user
        for i in xrange(10):
            self.guardian.monitor_queues(self.management_api.queues())
            time.sleep(0.2)

        # Terminate the consumer process
        self.terminate_proc()

        # Queue should still exist.
        self._wait_for_queue(self.consumer_cfg)

        # Get the queue's object
        db_session.refresh(self.user)

        self.assertTrue(len(self.user.queues) > 0)

        # Queue multiple messages while no consumer exists.
        for i in xrange(config.del_queue_size + 1):
            msg = self._build_message(i)
            self.publisher.publish(msg)

        # Wait some time for published messages to be taken into account
        for i in xrange(10):
            time.sleep(0.3)
            queues_to_delete = {q_data['name'] for q_data in self.management_api.queues()
                                if q_data['messages_ready'] > config.del_queue_size}
            if queues_to_delete:
                break

        # Tests that there are some queues that should be deleted
        self.assertTrue(len(queues_to_delete) > 0)

        # Monitor the queues, this should create the queue object and assign it to the user
        for i in xrange(20):
            self.guardian.monitor_queues(self.management_api.queues())
            time.sleep(0.2)

        # Tests that the queues that had to be deleted were deleted
        self.assertTrue(not any(q in queues_to_delete for q in self.management_api.queues()))
        # And that those were deleted by guardian
        self.assertEqual(queues_to_delete, self.guardian.deleted_queues)
        # And no queue have overgrown
        queues_to_delete = [q_data['name'] for q_data in self.management_api.queues()
                            if q_data['messages_ready'] > config.del_queue_size]
        self.assertTrue(len(queues_to_delete) == 0)

        # Reinitialize the db
        init_and_clear_db()



class ModelTest(unittest.TestCase):

    """Tests the underlying model (users and queues)
    """

    def setUp(self):
        Queue.query.delete()
        User.query.delete()

    def tearDown(self):
        Queue.query.delete()
        User.query.delete()

    def test_user(self):
        user = User.new_user(email='dUmMy@EmAil.com',
                             username='dummy', password='DummyPassword')
        self.assertTrue(user.valid_password('DummyPassword'))
        self.assertFalse(user.valid_password('dummypassword'))
        self.assertFalse(user.valid_password('DUMMYPASSWORD'))

        db_session.add(user)
        db_session.commit()

        self.assertIn(user, User.query.all())
        # Emails are normalized by putting them lower-case
        self.assertEqual(User.query.filter(User.email == 'dummy@email.com').first(), user)
        self.assertEqual(User.query.filter(User.username == 'dummy').first(), user)
        self.assertIsNone(User.query.filter(User.username == 'DOMMY').first())


class TestMessage(GenericMessage):

    def __init__(self):
        super(TestMessage, self).__init__()
        self.routing_parts.append('test')


def main(pulse_opts):
    global pulse_cfg
    pulse_cfg.update(pulse_opts)
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
    (opts, args) = parser.parse_args()
    main(opts.__dict__)
