# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import logging.handlers
import re
import time

import config
from model.base import init_db, db_session
from model.user import PulseUser
from model.queue import Queue
from management import PulseManagementAPI
from sendemail import sendemail

handler = logging.handlers.RotatingFileHandler(
    config.GUARDIAN_LOG_PATH,
    mode='a+',
    maxBytes=config.MAX_LOG_SIZE,
    backupCount=config.BACKUP_COUNT)
formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s",
                              "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

logging.getLogger().addHandler(handler)

if config.DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)


class PulseGuardian(object):
    """Monitors RabbitMQ queues: assigns owners to queues, warn owners
    when a queue have a dangerously high number of unread messages, and
    deletes a queue if its unread messages exceed an even higher threshold.

    :param api: An instance of PulseManagementAPI, to communicate with rabbitmq.
    :param emails: Sends emails to queue owners if True.
    :param warn_queue_size: Warning threshold.
    :param del_queue_size: Deletion threshold.
    :param on_warn: Callback called with a queue's name when it's warned.
    :param on_delete: Callback called with a queue's name when it's deleted.
    """
    def __init__(self, api, emails=True, warn_queue_size=config.warn_queue_size,
                 del_queue_size=config.del_queue_size, on_warn=None,
                 on_delete=None):
        if del_queue_size < warn_queue_size:
            raise ValueError("Deletion threshold can't be smaller than the "
                             "warning threshold.")

        self.api = api

        self.emails = emails
        self.warn_queue_size = warn_queue_size
        self.del_queue_size = del_queue_size

        self.on_warn = on_warn
        self.on_delete = on_delete

    def clear_deleted_queues(self, queues):
        db_queues = Queue.query.all()

        # Filter queues that are in the database but no longer on RabbitMQ.
        alive_queues_names = set(q['name'] for q in queues)
        deleted_queues = set(q for q in db_queues if q.name
                             not in alive_queues_names)

        # Delete those queues.
        for queue in deleted_queues:
            logging.info("Queue '{0}' has been deleted.".format(queue))
            db_session.delete(queue)
        db_session.commit()

    def update_queue_information(self, queue_data):
        if not 'messages' in queue_data:
            # FIXME: We should do something here, probably delete the queue,
            # as it's in a weird state.  More investigation is required.
            # See bug 1066338.
            return None

        q_size, q_name = (queue_data['messages'],
                          queue_data['name'])
        queue = Queue.query.filter(Queue.name == q_name).first()

        # If the queue doesn't exist in the db, create it.
        if queue is None:
            m = re.match('queue/([^/]+)/', q_name)
            logging.info("New queue '{0}' encountered. "
                        "Adding to the database.".format(q_name))
            if m:
                owner_name = m.group(1)
                owner = PulseUser.query.filter(
                    PulseUser.username == owner_name).first()

                # If the queue was created by a user that isn't in the
                # pulseguardian database, skip the queue.
                if owner is None:
                    logging.info(
                        "Queue '{0}' owner, {1}, isn't in the db. Creating "
                        "the user.".format(q_name, owner_name))
                    owner = PulseUser.new_user(owner_name)

                # Assign the user to the queue.
                logging.info("Assigning queue '{0}' to user "
                             "{1}.".format(q_name, owner))
            else:
                logging.warn("'{0}' is not a standard queue name.")
                owner = None
            queue = Queue(name=q_name, owner=owner)

        # Update the saved queue size.
        queue.size = q_size
        db_session.add(queue)
        db_session.commit()
        return queue

    def monitor_queues(self, queues):
        for queue_data in queues:
            # Updating the queue's information in the database (owner, size).
            queue = self.update_queue_information(queue_data)
            if not queue:
                continue

            # If a queue is over the deletion size, regardless of it having an
            # owner or not, delete it.
            if queue.size > self.del_queue_size:
                logging.warning("Queue '{0}' deleted. Queue size = {1}; "
                               "del_queue_size = {2}".format(
                    queue.name, queue.size, self.del_queue_size))
                if queue.owner and queue.owner.owner:
                    self.deletion_email(queue.owner.owner, queue_data)
                if self.on_delete:
                    self.on_delete(queue.name)
                self.api.delete_queue(vhost=queue_data['vhost'],
                                      queue=queue.name)
                db_session.delete(queue)
                db_session.commit()
                continue

            if queue.owner is None or queue.owner.owner is None:
                continue

            if queue.size > self.warn_queue_size and not queue.warned:
                logging.warning("Warning queue '{0}' owner. Queue size = {1}; "
                               "warn_queue_size = {2}".format(
                    queue.name, queue.size, self.warn_queue_size))
                queue.warned = True
                if self.on_warn:
                    self.on_warn(queue.name)
                self.warning_email(queue.owner.owner, queue_data)
            elif queue.size <= self.warn_queue_size and queue.warned:
                # A previously warned queue got out of the warning threshold;
                # its owner should not be warned again.
                logging.warning("Queue '{0}' was in warning zone but is OK "
                               "now".format(queue.name, queue.size,
                                            self.del_queue_size))
                queue.warned = False
                self.back_to_normal_email(queue.owner.owner, queue_data)

            # Commit any changes to the queue.
            db_session.add(queue)
            db_session.commit()

    def _exchange_from_queue(self, queue_data):
        exchange = 'could not be determined'
        detailed_data = self.api.queue(vhost=queue_data['vhost'],
                                       queue=queue_data['name'])
        if detailed_data['incoming']:
            exchange = detailed_data['incoming'][0]['exchange']['name']
        return exchange

    def warning_email(self, user, queue_data):
        exchange = self._exchange_from_queue(queue_data)

        subject = 'Pulse warning: queue "{0}" is overgrowing'.format(
            queue_data['name'])
        body = '''Warning: your queue "{0}" on exchange "{1}" is
overgrowing ({2} ready messages, {3} total messages).

The queue will be automatically deleted when it exceeds {4} messages.

Make sure your clients are running correctly and are cleaning up unused
durable queues.
'''.format(queue_data['name'], exchange, queue_data['messages_ready'],
           queue_data['messages'], self.del_queue_size)

        if self.emails and user.email is not None:
            sendemail(subject=subject, from_addr=config.email_from,
                      to_addrs=[user.email], username=config.email_account,
                      password=config.email_password, text_data=body)

    def deletion_email(self, user, queue_data):
        exchange = self._exchange_from_queue(queue_data)

        subject = 'Pulse warning: queue "{0}" has been deleted'.format(
            queue_data['name'])
        body = '''Your queue "{0}" on exchange "{1}" has been
deleted after exceeding the maximum number of unread messages.  Upon deletion
there were {2} messages in the queue, out of a maximum {3} messages.

Make sure your clients are running correctly and are cleaning up unused
durable queues.
'''.format(queue_data['name'], exchange, queue_data['messages'],
           self.del_queue_size)

        if self.emails and user.email is not None:
            sendemail(subject=subject, from_addr=config.email_from,
                      to_addrs=[user.email], username=config.email_account,
                      password=config.email_password, text_data=body)

    def back_to_normal_email(self, user, queue_data):
        exchange = self._exchange_from_queue(queue_data)

        subject = 'Pulse warning: queue "{0}" is back to normal'.format(
            queue_data['name'])
        body = '''Your queue "{0}" on exchange "{1}" is
now back to normal ({2} ready messages, {3} total messages).
'''.format(queue_data['name'], exchange, queue_data['messages_ready'],
           queue_data['messages'], self.del_queue_size)


        if self.emails and user.email is not None:
            sendemail(subject=subject, from_addr=config.email_from,
                      to_addrs=[user.email], username=config.email_account,
                      password=config.email_password, text_data=body)

    def guard(self):
        logging.info("PulseGuardian started")
        while True:
            queues = self.api.queues()
            if queues:
                self.monitor_queues(queues)
            self.clear_deleted_queues(queues)
            time.sleep(config.polling_interval)


if __name__ == '__main__':
    # Add StreamHandler for development purposes
    logging.getLogger().addHandler(logging.StreamHandler())

    # Initialize the database if necessary.
    init_db()

    api = PulseManagementAPI(host=config.rabbit_host,
                             management_port=config.rabbit_management_port,
                             user=config.rabbit_user,
                             password=config.rabbit_password)
    pulse_guardian = PulseGuardian(api)
    pulse_guardian.guard()
