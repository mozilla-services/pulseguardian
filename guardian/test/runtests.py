from mozillapulse.messages.base import GenericMessage
from mozillapulse.publishers import PulseTestPublisher

# Default RabbitMQ host settings are as defined in the accompanying
# vagrant puppet files.
DEFAULT_RABBIT_HOST = 'localhost'
DEFAULT_RABBIT_PORT = 5672
DEFAULT_RABBIT_VHOST = '/'
DEFAULT_RABBIT_USER = 'guest'
DEFAULT_RABBIT_PASSWORD = 'guest'

# Global pulse configuration.
pulse_cfg = {}

class TestMessage(GenericMessage):

    def __init__(self):
        super(TestMessage, self).__init__()
        self.routing_parts.append('test')

if __name__ == '__main__':
    publisher = PulseTestPublisher()
    for i in xrange(10):
        msg = TestMessage()
        publisher.publish(msg)
