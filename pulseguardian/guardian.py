# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import re
import requests
import socket
import time
import traceback

from pulseguardian import config, management as pulse_management
from pulseguardian.logs import setup_logging
from pulseguardian.model.base import init_db, db_session
from pulseguardian.model.binding import Binding
from pulseguardian.model.user import PulseUser, User
from pulseguardian.model.queue import Queue
from pulseguardian.sendemail import sendemail

logging.getLogger("requests").setLevel(logging.WARNING)

setup_logging(config.guardian_log_path)


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
    def __init__(self, emails=True, warn_queue_size=config.warn_queue_size,
                 del_queue_size=config.del_queue_size, on_warn=None,
                 on_delete=None):
        if del_queue_size < warn_queue_size:
            raise ValueError("Deletion threshold can't be smaller than the "
                             "warning threshold.")

        self.emails = emails
        self.warn_queue_size = warn_queue_size
        self.del_queue_size = del_queue_size
        self.on_warn = on_warn
        self.on_delete = on_delete
        self._polling_interval = config.polling_interval
        self._connection_error_notified = False
        self._unknown_error_notified = False

    def _increase_interval(self):
        if self._polling_interval < config.polling_max_interval:
            self._polling_interval += config.polling_interval

    def _reset_notification_error_params(self):
        self._polling_interval = config.polling_interval
        self._connection_error_notified = False
        self._unknown_error_notified = False

    def _sendemail(self, to_addrs, subject, text_data):
        sendemail(subject=subject,
                  from_addr=config.email_from,
                  to_addrs=to_addrs,
                  username=config.email_account,
                  password=config.email_password,
                  text_data=text_data,
                  server=config.email_smtp_server,
                  port=config.email_smtp_port,
                  use_ssl=config.email_ssl)

    def get_queue_bindings(self, all_bindings, queue_name):
        """Extract the bindigns for just the named queue"""
        return [x for x in all_bindings if
                x["destination_type"] == "queue" and
                x["destination"] == queue_name]

    def clear_deleted_queues(self, queues, all_bindings):
        db_queues = Queue.query.all()

        # Filter queues that are in the database but no longer on RabbitMQ.
        alive_queues_names = {q['name'] for q in queues}
        deleted_queues = {q for q in db_queues
                          if q.name not in alive_queues_names}

        # Delete those queues.
        for queue in deleted_queues:
            logging.debug("Queue '{0}' has been deleted.".format(queue))
            db_session.delete(queue)

        # Clean up bindings on queues that are not deleted.
        for queue_name in alive_queues_names:
            bindings = self.get_queue_bindings(all_bindings, queue_name)
            self.clear_deleted_bindings(queue_name, bindings)

        db_session.commit()

    def clear_deleted_bindings(self, queue_name, queue_bindings):
        db_bindings = Binding.query.filter(Binding.queue_name == queue_name)

        # Filter bindings that are in the database but no longer on RabbitMQ.
        alive_bindings_names = {Binding.as_string(b['source'], b['routing_key'])
                                for b in queue_bindings}
        deleted_bindings = {b for b in db_bindings
                            if b.name not in alive_bindings_names}

        # Delete those bindings.
        for binding in deleted_bindings:
            logging.debug("Binding '{}' for queue '{}' has been deleted.".format(
                binding, queue_name))
            db_session.delete(binding)

    def update_queue_information(self, queue_data, all_bindings):
        if not 'messages' in queue_data:
            # FIXME: We should do something here, probably delete the queue,
            # as it's in a weird state.  More investigation is required.
            # See bug 1066338.
            return None

        q_size, q_name, q_durable = (queue_data['messages'],
                                     queue_data['name'],
                                     queue_data['durable'])
        queue = Queue.query.filter(Queue.name == q_name).first()

        # If the queue doesn't exist in the db, create it.
        if queue is None:
            m = re.match('queue/([^/]+)/', q_name)
            logging.debug("New queue '{0}' encountered. "
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
                logging.debug("Assigning queue '{0}' to user "
                              "{1}.".format(q_name, owner))
            else:
                logging.warn("'{0}' is not a standard queue name.".format(
                    q_name))
                owner = None
            queue = Queue(name=q_name, owner=owner)

        # add the queue bindings to the db.
        bindings = self.get_queue_bindings(all_bindings, queue.name)
        for binding in bindings:
            db_binding = Binding.query.filter(
                Binding.exchange == binding["source"],
                Binding.routing_key == binding["routing_key"],
                Binding.queue_name == queue.name
                ).first()

            if not db_binding:
                # need to create the binding in the DB
                binding = Binding(exchange=binding["source"],
                                  routing_key=binding["routing_key"],
                                  queue_name=queue.name)
                db_session.add(binding)

        # Update the saved queue size.
        queue.size = q_size
        queue.durable = q_durable
        db_session.add(queue)
        db_session.commit()
        return queue

    def monitor_queues(self, queues, all_bindings):
        for queue_data in queues:
            # Updating the queue's information in the database (owner, size).
            queue = self.update_queue_information(queue_data, all_bindings)
            if not queue:
                continue

            # If a queue is over the deletion size and ``unbounded`` is
            # False (the default), then delete it regardless of it having
            # an owner or not
            # If ``unbounded`` is True, then let it grow indefinitely.
            if queue.size > self.del_queue_size and not queue.unbounded:
                logging.warning("Queue '{0}' deleted. Queue size = {1}; "
                               "del_queue_size = {2}".format(
                    queue.name, queue.size, self.del_queue_size))
                if queue.owner and queue.owner.owner:
                    self.deletion_email(queue.owner.owner, queue_data)
                if self.on_delete:
                    self.on_delete(queue.name)
                pulse_management.delete_queue(vhost=queue_data['vhost'],
                                              queue=queue.name)
                db_session.delete(queue)
                db_session.commit()
                continue

            if queue.owner is None or queue.owner.owner is None:
                continue

            if queue.size > self.warn_queue_size and not queue.warned:
                logging.warning("Warning queue '{0}' owner. Queue size = "
                                "{1}; warn_queue_size = {2}".format(
                                    queue.name, queue.size,
                                    self.warn_queue_size))
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
        detailed_data = pulse_management.queue(vhost=queue_data['vhost'],
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
            self._sendemail(
                subject=subject, to_addrs=[user.email], text_data=body)

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
            self._sendemail(
                subject=subject, to_addrs=[user.email], text_data=body)

    def back_to_normal_email(self, user, queue_data):
        exchange = self._exchange_from_queue(queue_data)

        subject = 'Pulse warning: queue "{0}" is back to normal'.format(
            queue_data['name'])
        body = '''Your queue "{0}" on exchange "{1}" is
now back to normal ({2} ready messages, {3} total messages).
'''.format(queue_data['name'], exchange, queue_data['messages_ready'],
           queue_data['messages'], self.del_queue_size)

        if self.emails and user.email is not None:
            self._sendemail(
                subject=subject, to_addrs=[user.email], text_data=body)

    def notify_connection_error(self):
        """Log and email to admin(s) that a connection error occurred.

        Note that this function expects to be called from within an
        exception handler.
        """
        ex_details = traceback.format_exc()
        errmsg = '''Could not connect to Pulse.

Rabbit URL: {0}
Rabbit user: {1}
Error:
{2}
'''.format(config.rabbit_management_url, config.rabbit_user, ex_details)

        logging.error(errmsg)

        if self.emails and not self._connection_error_notified:
            admin_emails = [user.email for user
                            in User.query.filter_by(admin=True)]
            subject = "PulseGuardian error: Can't connect to Pulse"

            self._sendemail(
                subject=subject, to_addrs=admin_emails, text_data=errmsg)
            self._connection_error_notified = True

    def notify_unknown_error(self):
        """Log and email to admin(s) that an unexpected error occurred.

        Note that this function expects to be called from within an
        exception handler.
        """
        ex_details = traceback.format_exc()
        errmsg = '''Unknown error occured.

Rabbit URL: {0}
Rabbit user: {1}
Error:
{2}
'''.format(config.rabbit_management_url, config.rabbit_user, ex_details)

        logging.error(errmsg)

        if self.emails and not self._unknown_error_notified:
            admin_emails = [user.email for user
                            in User.query.filter_by(admin=True)]
            subject = "PulseGuardian error: Unknown error"

            self._sendemail(
                subject=subject, to_addrs=admin_emails, text_data=body)
            self._unknown_error_notified = True

    def guard(self):
        logging.info("PulseGuardian started")

        while True:
            logging.info('Guard loop.')
            try:
                queues = pulse_management.queues()
                bindings = pulse_management.bindings()

                logging.info('Got queues')

                if queues:
                    logging.info('Monitor queues')
                    self.monitor_queues(queues, bindings)

                logging.info('Clear deleted queues')
                self.clear_deleted_queues(queues, bindings)

                if (self._connection_error_notified or
                        self._unknown_error_notified):
                    self._reset_notification_error_params()
            except (requests.ConnectionError, socket.error):
                self.notify_connection_error()
                self._increase_interval()
            except KeyboardInterrupt:
                break
            except Exception:
                self.notify_unknown_error()
                self._increase_interval()

            logging.info('Sleeping for %d seconds' % self._polling_interval)
            time.sleep(self._polling_interval)

if __name__ == '__main__':
    # Add StreamHandler for development purposes
    logging.getLogger().addHandler(logging.StreamHandler())

    # Initialize the database if necessary.
    init_db()

    pulse_guardian = PulseGuardian()
    pulse_guardian.guard()
