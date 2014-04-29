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
        return requests.get('{}/{}'.format(API_BASE_URL, path), auth=(DEFAULT_RABBIT_USER, DEFAULT_RABBIT_PASSWORD)).json()
    
    def queues(self):
        return self._api_request('queues')
    
    def vhosts(self):
        return self._api_request('vhosts')

if __name__ == '__main__':
    api = PulseManagementAPI()
    print api.queues()
    print api.vhosts()