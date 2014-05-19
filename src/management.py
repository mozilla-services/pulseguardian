from urllib import quote
import json

import requests

DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_MANAGEMENT_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'


class PulseManagementException(Exception):
    pass


class PulseManagementAPI(object):

    def __init__(self, host=DEFAULT_RABBIT_HOST,
                 management_port=DEFAULT_RABBIT_MANAGEMENT_PORT,
                 user=DEFAULT_RABBIT_USER,
                 password=DEFAULT_RABBIT_PASSWORD):
        self.host = host
        self.management_port = management_port
        self.management_user = user
        self.management_password = password

    def _api_request(self, path, method='GET', data=None):
        session = requests.Session()
        request = requests.Request(
            method, 'http://{}:{}/api/{}'.format(
                self.host, self.management_port, path),
            auth=(self.management_user, self.management_password),
            data=json.dumps(data)).prepare()
        request.headers['Content-type'] = 'application/json'
        response = session.send(request)

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            raise PulseManagementException(
                "Error when calling '{} {}' with data={}. Received : {}".format(method, path, data, response.content))

    # Queues

    def queues(self, vhost=None):
        if vhost:
            vhost = quote(vhost, '')
            return self._api_request('queues/{}'.format(vhost))
        else:
            return self._api_request('queues')

    def queue(self, vhost, queue):
        vhost = quote(vhost, '')
        queue = quote(queue, '')
        return self._api_request('queues/{}/{}'.format(vhost, queue))

    def purge_queue(self, vhost, queue):
        vhost = quote(vhost, '')
        queue = quote(queue, '')
        return self._api_request('/api/queues/{}/{}/contents'.format(vhost,
                                                                     queue))

    def queue_messages(self, vhost, queue, count, truncate=None, requeue=True,
                       encoding='auto'):
        vhost = quote(vhost, '')
        queue = quote(queue, '')

        data = dict(count=count, requeue=requeue, encoding=encoding)
        if truncate:
            data['truncate'] = truncate

        return self._api_request('/api/queues/{}/{}/get'.format(vhost, queue),
                                 method='POST', data=data)

    def delete_queue(self, vhost, queue):
        vhost = quote(vhost, '')
        queue = quote(queue, '')
        self._api_request('queues/{}/{}'.format(vhost, queue), method='DELETE')

    def delete_all_queues(self):
        for queue_data in self.queues():
            self.delete_queue(queue_data['vhost'], queue_data['name'])

    # Users

    def user(self, username):
        username = quote(username, '')
        return self._api_request('users/{}'.format(username))

    def create_user(self, username, password, tags='monitoring'):
        username = quote(username, '')
        data = dict(password=password, tags=tags)
        self._api_request('users/{}'.format(username), method='PUT', data=data)

    def delete_user(self, username):
        username = quote(username, '')
        self._api_request('users/{}'.format(username), method='DELETE')

    # Permissions

    def permissions(self):
        return self._api_request('permissions')

    def permission(self, username, vhost):
        username = quote(username, '')
        vhost = quote(vhost, '')
        return self._api_request('permissions/{}/{}'.format(vhost, username))

    def set_permission(self, username, vhost, configure='', write='', read=''):
        username = quote(username, '')
        vhost = quote(vhost, '')
        data = dict(configure=configure, write=write, read=read)
        self._api_request('permissions/{}/{}'.format(
            vhost, username), method='PUT', data=data)

    # Channels

    def channels(self):
        return self._api_request('channels')

    def channel(self, channel):
        channel = quote(channel, '')
        return self._api_request('channels/{}'.format(channel))

    # Exchanges

    def exchanges(self, vhost=None):
        if vhost:
            vhost = quote(vhost, '')
            return self._api_request('exchanges/{}'.format(vhost))
        else:
            return self._api_request('exchanges')

    def exchange(self, vhost, name):
        vhost = quote(vhost, '')
        name = quote(name, '')
        return self._api_request('exchanges/{}/{}'.format(vhost, name))

    def create_exchange(self, vhost, name, type="direct", auto_delete=False,
                        durable=True, internal=False, arguments=None):
        arguments = arguments or list()
        vhost = quote(vhost, '')
        name = quote(name, '')

        data = dict(type=type, auto_delete=auto_delete,
                    durable=durable, internal=internal, arguments=arguments)
        self._api_request('exchanges/{}/{}'.format(
            vhost, name), method='PUT', data=data)

    # Misc

    def queue_owner(self, queue_data):
        queue = self.queue(vhost=queue_data['vhost'], queue=queue_data['name'])

        if queue['consumers'] < 1:
            return None

        channel_name = queue['consumer_details'][0]['channel_details']['name']
        channel = self.channel(channel_name)
        return channel['user']
