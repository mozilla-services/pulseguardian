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


if __name__ == '__main__':
    api = PulseManagementAPI()
    for queue in api.queues(vhost=DEFAULT_RABBIT_VHOST):
        print "Queue '{}' : {} messages".format(queue['name'], queue['messages_ready'])