import time

import requests

DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_MANAGEMENT_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'

WARN_QUEUE_SIZE = 2
ARCHIVE_QUEUE_SIZE = 15
DEL_QUEUE_SIZE = 20

POLLING_INTERVAL = 2

class PulseManagementAPI(object):
    def __init__(self, host=DEFAULT_RABBIT_HOST, management_port=DEFAULT_RABBIT_MANAGEMENT_PORT, vhost=DEFAULT_RABBIT_VHOST,
        user=DEFAULT_RABBIT_USER, password=DEFAULT_RABBIT_PASSWORD):

        self.host = host
        self.management_port = management_port
        self.vhost = vhost
        self.user = user
        self.password = password
    
    def _api_request(self, path):
        response = requests.get('http://{}:{}/api/{}'.format(self.host, self.management_port, path),
                                 auth=(self.user, self.password))
        try:
            return response.json()
        except ValueError:
            raise ValueError("Error when calling the API with path '{}'. Received : {}".format(path, response.content))

    def queues(self, vhost=None):
        if vhost:
            return self._api_request('queues/{}'.format(vhost))
        else:
            return self._api_request('queues')
    
    def queue_details(self, vhost, queue):
        return self._api_request('queues/{}/{}'.format(vhost, queue))


    def vhosts(self):
        return self._api_request('vhosts')

class PulseGuardian(object):

    def __init__(self, api, warn_queue_size=WARN_QUEUE_SIZE, archive_queue_size=ARCHIVE_QUEUE_SIZE, del_queue_size=DEL_QUEUE_SIZE):
        self.api = api

        self.warn_queue_size = warn_queue_size
        self.archive_queue_size = archive_queue_size
        self.del_queue_size = del_queue_size

    def guard(self):
        while True:
            for queue in api.queues(vhost=DEFAULT_RABBIT_VHOST):
                if queue['messages_ready'] > self.warn_queue_size:
                    print "Warn queue '{}' owner. Queue size = {} ; warn_queue_size = {}".format(queue['name'], queue['messages_ready'], self.warn_queue_size)

            # Sleeping
            time.sleep(POLLING_INTERVAL)

if __name__ == '__main__':
    api = PulseManagementAPI()
    pulse_guardian = PulseGuardian(api)

    pulse_guardian.guard()