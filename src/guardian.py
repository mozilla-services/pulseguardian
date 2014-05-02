import time
import logging

from model.base import init_db, db_session
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI
from sendemail import sendemail
import config

WARN_QUEUE_SIZE = 2
ARCHIVE_QUEUE_SIZE = 15
DEL_QUEUE_SIZE = 20
POLLING_INTERVAL = 2

class PulseGuardian(object):

    def __init__(self, api, warn_queue_size=WARN_QUEUE_SIZE, archive_queue_size=ARCHIVE_QUEUE_SIZE, del_queue_size=DEL_QUEUE_SIZE):
        self.api = api

        self.warn_queue_size = warn_queue_size
        self.archive_queue_size = archive_queue_size
        self.del_queue_size = del_queue_size

        self.warned = set()

    def monitor_queues(self, queues):
        for queue_data in queues:
            q_size, q_name = queue_data['messages_ready'], queue_data['name']

            queue = Queue.query.filter(Queue.name == q_name).first()

            # If the queue doesn't exist, we create it
            if queue is None:
                queue = Queue(name=q_name, owner=None)
                db_session.add(queue)
                db_session.commit()

            # If we don't know who created the queue
            if queue.owner is None:
                # If no client is currently consuming the queue, we just skip it
                if queue_data['consumers'] == 0:
                    continue

                # Otherwise we look for its user
                owner_name = self.api.queue_owner(queue_data)

                user = User.query.filter(User.username == owner_name).first()

                # If the queue was created by a user that isn't in the pulseguardian database, we skip the queue
                if user is None:
                    continue

                # We assign the user to the queue
                queue.owner = user

                db_session.add(queue)
                db_session.commit()

            if q_size > self.del_queue_size:
                logging.warning("Queue '{}' is going to be deleted. Queue size = {} ; del_queue_size = {}".format(q_name, q_size, self.del_queue_size))
                # Send mail here
            elif q_size > self.warn_queue_size and not q_name in self.warned:
                logging.warning("Should warn'{}' owner. Queue size = {} ; warn_queue_size = {}".format(q_name, q_size, self.warn_queue_size))
                # Delete queue here
                self.warned.add(q_name)
            elif q_size <= self.warn_queue_size and q_name in self.warned:
                # When a warned queue gets out of the warning threshold, it can get warned again
                self.warned.remove(q_name)

    def warning_email(self, user, queue_data):
        # TODO : improve warning reporting with an HTML template
        sendemail(subject="Activate your Pulse account", from_addr=config.email_from, to_addrs=[user.email],
                  username=config.email_account, password=config.email_password,
                  text_data='Warning. Your queue "{}" is overgrowing.'.format(queue_data['name']))

    def guard(self):
        while True:
            queues = self.api.queues()
            
            self.monitor_queues(queues)

            # Sleeping
            time.sleep(POLLING_INTERVAL)

if __name__ == '__main__':
    init_db()

    api = PulseManagementAPI()
    pulse_guardian = PulseGuardian(api)

    pulse_guardian.guard()