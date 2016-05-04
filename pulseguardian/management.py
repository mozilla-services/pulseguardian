# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Wrapper functions around the RabbitMQ management plugin's REST API."""

import json
import logging
from urllib import quote

import requests

from pulseguardian import config

class PulseManagementException(Exception):
    pass


def _api_request(path, method='GET', data=None):
    session = requests.Session()
    url = '{0}{1}'.format(config.rabbit_management_url, path)
    request = requests.Request(method, url,
                               auth=(config.rabbit_user,
                                     config.rabbit_password),
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

def queues(vhost=None):
    if vhost:
        vhost = quote(vhost, '')
        return _api_request('queues/{0}'.format(vhost))
    else:
        return _api_request('queues')


def queue(vhost, queue):
    vhost = quote(vhost, '')
    queue = quote(queue, '')
    return _api_request('queues/{0}/{1}'.format(vhost, queue))


def queue_bindings(vhost, queue):
    vhost = quote(vhost, '')
    queue = quote(queue, '')
    bindings = _api_request('queues/{0}/{1}/bindings'.format(vhost, queue))
    return [b for b in bindings if b["source"]]


def delete_queue(vhost, queue):
    vhost = quote(vhost, '')
    queue = quote(queue, '')
    _api_request('queues/{0}/{1}'.format(vhost, queue),
                      method='DELETE')


def delete_all_queues():
    for queue_data in queues():
        delete_queue(queue_data['vhost'], queue_data['name'])


# Users

def user(username):
    username = quote(username, '')
    return _api_request('users/{0}'.format(username))


def create_user(username, password, tags=''):
    username = quote(username, '')
    data = dict(password=password, tags=tags)
    _api_request('users/{0}'.format(username), method='PUT',
                      data=data)


def delete_user(username):
    username = quote(username, '')
    _api_request('users/{0}'.format(username), method='DELETE')


# Permissions

def set_permission(username, vhost, configure='', write='', read=''):
    username = quote(username, '')
    vhost = quote(vhost, '')
    data = dict(configure=configure, write=write, read=read)
    _api_request('permissions/{0}/{1}'.format(
        vhost, username), method='PUT', data=data)


# Channels

def channel(channel):
    channel = quote(channel, '')
    return _api_request('channels/{0}'.format(channel))
