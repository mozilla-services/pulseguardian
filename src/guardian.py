import time
import logging

from model.base import init_db, db_session
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI
from sendemail import sendemail
import config


class PulseGuardian(object):

    def __init__(self, api, emails=True, warn_queue_size=config.warn_queue_size,
                 archive_queue_size=config.archive_queue_size,
                 del_queue_size=config.del_queue_size):
        self.api = api

        self.emails = emails
        self.warn_queue_size = warn_queue_size
        self.archive_queue_size = archive_queue_size
        self.del_queue_size = del_queue_size

        self.warned_queues = set()
        self.deleted_queues = set()

    def monitor_queues(self, queues):
        for queue_data in queues:
            q_size, q_name, q_vhost = queue_data[
                'messages_ready'], queue_data['name'], queue_data['vhost']
            queue = Queue.query.filter(Queue.name == q_name).first()

            # If the queue doesn't exist, we create it
            if queue is None:
                logging.warning(
                    ". New queue '{}' encountred. Adding to the databse.".format(q_name))
                queue = Queue(name=q_name, owner=None)
                db_session.add(queue)
                db_session.commit()

            # Updating the saved queue size
            queue.size = q_size

            # If a queue is over the deletion size, regardless of it having an
            # owner or not, we delete it
            if q_size > self.del_queue_size:
                logging.warning("Queue '{}' deleted. Queue size = {}; del_queue_size = {}".format(
                    q_name, q_size, self.del_queue_size))
                self.deleted_queues.add(queue.name)
                self.api.delete_queue(vhost=q_vhost, queue=q_name)
                if queue.owner and self.emails:
                    self.deletion_email(queue.owner, queue_data)
                db_session.delete(queue)
                db_session.commit()
                continue

            # If we don't know who created the queue
            if queue.owner is None:
                # logging.info('. Queue "{}" owner unknown.'.format(q_name))

                # If no client is currently consuming the queue, we just skip
                # it
                if queue_data['consumers'] == 0:
                    # logging.info(". Queue '{}' skipped (no owner, no current consumer).".format(q_name))
                    continue

                # Otherwise we look for its user
                owner_name = self.api.queue_owner(queue_data)

                user = User.query.filter(User.username == owner_name).first()

                # If the queue was created by a user that isn't in the
                # pulseguardian database, we skip the queue
                if user is None:
                    logging.warning(
                        ". Queue '{}' owner, {}, isn't in the db. Skipping the queue.".format(q_name, owner_name))
                    continue

                # We assign the user to the queue
                logging.warning(
                    ". Assigning queue '{}'  to user {}.".format(q_name, user))
                queue.owner = user

            # print q_size, queue
            if q_size > self.warn_queue_size and not queue.warned:
                logging.warning("Warning queue '{}' owner. Queue size = {} ; warn_queue_size = {}".format(
                    q_name, q_size, self.warn_queue_size))
                queue.warned = True
                self.warned_queues.add(queue.name)
                if self.emails:
                    self.warning_email(queue.owner, queue_data)
            elif q_size <= self.warn_queue_size and queue.warned:
                logging.warning("Queue '{}' was in warning zone but is OK now".format(
                    q_name, q_size, self.del_queue_size))
                # When a warned queue gets out of the warning threshold, it can
                # get warned again
                queue.warned = False

            # Commiting changes to the queue
            db_session.add(queue)
            db_session.commit()

    def warning_email(self, user, queue_data):
        exchange = 'could not be determined'
        detailed_data = self.api.queue(
            vhost=queue_data['vhost'], queue=queue_data['name'])
        if detailed_data['incoming']:
            exchange = detailed_data['incoming'][0]['exchange']['name']
        sendemail(
            subject="Pulse : Overgrowing queue warning", from_addr=config.email_from, to_addrs=[user.email],
            username=config.email_account, password=config.email_password,
            text_data="Warning. Your queue '{}' on the exchange '{}' is overgrowing.\
                   Make sure your clients are running correctly.".format(queue_data['name'], exchange))

    def deletion_email(self, user, queue_data):
        exchange = 'could not be determined'
        detailed_data = self.api.queue(
            vhost=queue_data['vhost'], queue=queue_data['name'])
        if detailed_data['incoming']:
            exchange = detailed_data['incoming'][0]['exchange']['name']
        sendemail(
            subject="Pulse : Deleted an overgrowing queue", from_addr=config.email_from, to_addrs=[user.email],
            username=config.email_account, password=config.email_password,
            text_data="Your queue '{}' on the exchange '{}' has been deleted because it exceeded the unread messages limit.\n\
                  Make sure your clients are running correctly and delete unused queues.".format(queue_data['name'], exchange))

    def guard(self):
        while True:
            queues = self.api.queues()
            self.monitor_queues(queues)
            # Sleeping
            time.sleep(config.polling_interval)

if __name__ == '__main__':
    # Initializing the databse
    init_db()

    api = PulseManagementAPI(
        host=config.rabbit_host, management_port=config.rabbit_management_port, vhost=config.rabbit_vhost,
        user=config.rabbit_user, password=config.rabbit_password)
    pulse_guardian = PulseGuardian(api)
    pulse_guardian.guard()
