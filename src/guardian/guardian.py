import time
import logging
import json

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

class PulseManagementException(Exception):
    pass

class PulseManagementAPI(object):

    def __init__(self, host=DEFAULT_RABBIT_HOST, management_port=DEFAULT_RABBIT_MANAGEMENT_PORT, vhost=DEFAULT_RABBIT_VHOST,
        user=DEFAULT_RABBIT_USER, password=DEFAULT_RABBIT_PASSWORD):

        self.host = host
        self.management_port = management_port
        self.vhost = vhost
        self.user = user
        self.password = password
    
    def _api_request(self, path, method='GET', data=None):
        session = requests.Session()
        request = requests.Request(method, 'http://{}:{}/api/{}'.format(self.host, self.management_port, path),
                                   auth=(self.user, self.password), data=json.dumps(data)).prepare()
        request.headers['Content-type'] = 'application/json'
        response = session.send(request)

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            raise PulseManagementException("Error when calling '{} {}' with data={}. Received : {}".format(method, path, data, response.content))

    def queues(self, vhost=None):
        if vhost:
            return self._api_request('queues/{}'.format(vhost))
        else:
            return self._api_request('queues')
    
    def queue(self, vhost, queue):
        return self._api_request('queues/{}/{}'.format(vhost, queue))

    def vhosts(self):
        return self._api_request('vhosts')

    def create_user(self, username, password, tags='monitoring'):
        data = dict(password=password, tags=tags)
        self._api_request('users/{}'.format(username), method='PUT', data=data)

class PulseGuardian(object):

    def __init__(self, api, warn_queue_size=WARN_QUEUE_SIZE, archive_queue_size=ARCHIVE_QUEUE_SIZE, del_queue_size=DEL_QUEUE_SIZE):
        self.api = api

        self.warn_queue_size = warn_queue_size
        self.archive_queue_size = archive_queue_size
        self.del_queue_size = del_queue_size

        self.warned = set()

    def guard(self):
        while True:
            for queue in api.queues(vhost=DEFAULT_RABBIT_VHOST):
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

    api.create_user('testuser', 'testpass')

    pulse_guardian.guard()