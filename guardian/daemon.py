import requests

DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_API_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'
API_BASE_URL = 'http://{}:{}/api'.format(DEFAULT_RABBIT_HOST, DEFAULT_RABBIT_API_PORT)

class PulseManagementAPI(object):
    def _api_request(self, path):
        response = requests.get('{}/{}'.format(API_BASE_URL, path), auth=(DEFAULT_RABBIT_USER, DEFAULT_RABBIT_PASSWORD))
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