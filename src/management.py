import json
import requests

DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_MANAGEMENT_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'

class PulseManagementException(Exception):
    pass

class PulseManagementAPI(object):

    def __init__(self, host=DEFAULT_RABBIT_HOST, management_port=DEFAULT_RABBIT_MANAGEMENT_PORT, vhost=DEFAULT_RABBIT_VHOST,
        user=DEFAULT_RABBIT_USER, password=DEFAULT_RABBIT_PASSWORD):

        self.host = host
        self.management_port = management_port
        self.vhost = vhost
        self.management_user = user
        self.management_password = password
    
    def _api_request(self, path, method='GET', data=None):
        session = requests.Session()
        request = requests.Request(method, 'http://{}:{}/api/{}'.format(self.host, self.management_port, path),
                                   auth=(self.management_user, self.management_password), data=json.dumps(data)).prepare()
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

    def user(self, username):
        return self._api_request('users/{}'.format(username))

    def create_user(self, username, password, tags='monitoring'):
        data = dict(password=password, tags=tags)
        self._api_request('users/{}'.format(username), method='PUT', data=data)

    def delete_user(self, username):
        self._api_request('users/{}'.format(username), method='DELETE')

if __name__ == '__main__':
    api = PulseManagementAPI()

    api.create_user('testuser', 'testpass')
    
    user_info = api.user('testuser')
    assert user_info['name'] == 'testuser'
    assert user_info['tags'] == 'monitoring'
    api.delete_user('testuser')

    try:
        api.user('testuser')
        assert False
    except PulseManagementException:
        pass