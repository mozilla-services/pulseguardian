import time
import logging

from management import PulseManagementAPI

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

    def guard(self):
        while True:
            for queue in api.queues():
                q_size, q_name = queue['messages_ready'], queue['name']

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

            # Sleeping
            time.sleep(POLLING_INTERVAL)

if __name__ == '__main__':
    api = PulseManagementAPI()
    pulse_guardian = PulseGuardian(api)
    pulse_guardian.guard()