# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
from urllib import quote

import requests

class PulseManagementException(Exception):
    pass


class PulseManagementAPI(object):
    """Wrapper around the RabbitMQ management plugin's REST API.

    :param url: Management API URL.
    :param management_port: Port used by the management plugin.
    :param user: RabbitMQ user with administrator privilege.
    :param password: Password of the RabbitMQ user.
    """
    exception = PulseManagementException

    def __init__(self, management_url, user, password):
        self.management_url = management_url.rstrip('/') + '/'
        self.management_user = user
        self.management_password = password

    def _api_request(self, path, method='GET', data=None):
        session = requests.Session()
        url = '{0}{1}'.format(self.management_url, path)
        request = requests.Request(method, url,
                                   auth=(self.management_user,
                                         self.management_password),
                                   data=json.dumps(data)).prepare()
        request.headers['Content-type'] = 'application/json'
        response = session.send(request)

        if response is None or not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            raise PulseManagementException(
                "Error when calling '{0} {1}' with data={2}. "
                "Received: {3}".format(method, path, data, response.content))

    # Queues

    def queues(self, vhost=None):
        if vhost:
            vhost = quote(vhost, '')
            return self._api_request('queues/{0}'.format(vhost))
        else:
            return self._api_request('queues')

    def queue(self, vhost, queue):
        vhost = quote(vhost, '')
        queue = quote(queue, '')
        return self._api_request('queues/{0}/{1}'.format(vhost, queue))

    def delete_queue(self, vhost, queue):
        vhost = quote(vhost, '')
        queue = quote(queue, '')
        self._api_request('queues/{0}/{1}'.format(vhost, queue),
                          method='DELETE')

    def delete_all_queues(self):
        for queue_data in self.queues():
            self.delete_queue(queue_data['vhost'], queue_data['name'])

    # Users

    def user(self, username):
        username = quote(username, '')
        return self._api_request('users/{0}'.format(username))

    def create_user(self, username, password, tags=''):
        username = quote(username, '')
        data = dict(password=password, tags=tags)
        self._api_request('users/{0}'.format(username), method='PUT',
                          data=data)

    def delete_user(self, username):
        username = quote(username, '')
        self._api_request('users/{0}'.format(username), method='DELETE')

    # Permissions

    def set_permission(self, username, vhost, configure='', write='', read=''):
        username = quote(username, '')
        vhost = quote(vhost, '')
        data = dict(configure=configure, write=write, read=read)
        self._api_request('permissions/{0}/{1}'.format(
            vhost, username), method='PUT', data=data)

    # Channels

    def channel(self, channel):
        channel = quote(channel, '')
        return self._api_request('channels/{0}'.format(channel))
