import requests

DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_API_PORT = 15672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'


if __name__ == '__main__':
    api_url = 'http://{}:{}/api'.format(DEFAULT_RABBIT_HOST, DEFAULT_RABBIT_API_PORT)
    print api_url
    print requests.get('{}/vhosts'.format(api_url), auth=(DEFAULT_RABBIT_USER, DEFAULT_RABBIT_PASSWORD)).text