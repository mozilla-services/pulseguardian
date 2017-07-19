import base64
import os

# Web app
flask_host = os.getenv('FLASK_HOST', 'localhost')
flask_port = int(os.getenv('FLASK_PORT', 5000))
flask_use_ssl = bool(int(os.getenv('FLASK_USE_SSL', 1)))
flask_server_name = os.getenv('FLASK_SERVER_NAME', None)

if not flask_server_name:
    if ((flask_use_ssl and flask_port == 443) or
            (not flask_use_ssl and flask_port == 80)):
        flask_port_spec = ''
    else:
        flask_port_spec = ':{}'.format(flask_port)

    flask_server_name = '{}{}'.format(
        flask_host,
        flask_port_spec
    )

try:
    flask_secret_key = base64.b64decode(os.getenv('FLASK_SECRET_KEY', None))
except TypeError:
    raise Exception('FLASK_SECRET_KEY must be base64 encoded.')

flask_debug_mode = bool(int(os.getenv('FLASK_DEBUG_MODE', 1)))

# OIDC
oidc_domain = os.getenv('OIDC_DOMAIN', None)
oidc_client_id = os.getenv('OIDC_CLIENT_ID', None)
oidc_client_secret = os.getenv('OIDC_CLIENT_SECRET', None)

# Mail
email_account = os.getenv('EMAIL_ACCOUNT', 'automation@mozilla.com')
email_password = os.getenv('EMAIL_PASSWORD', None)
email_from = os.getenv('EMAIL_FROM', 'Mozilla A-Team <auto-tools@mozilla.com>')
email_smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.mozilla.org')
email_smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 25))
email_ssl = bool(int(os.getenv('EMAIL_SSL', 0)))

# Database
database_url = os.getenv('DATABASE_URL',
                         'postgresql://root@localhost/pulseguardian')
pool_recycle_interval = int(os.getenv('POOL_RECYCLE_INTERVAL', 60))

# RabbitMQ

# Management API URL.
rabbit_management_url = os.getenv('RABBIT_MANAGEMENT_URL',
                                  'http://localhost:15672/api/')
rabbit_vhost = os.getenv('RABBIT_VHOST', '/')

# RabbitMQ user with administrator privilege.
rabbit_user = os.getenv('RABBIT_USER', 'guest')
# Password of the RabbitMQ user.
rabbit_password = os.getenv('RABBIT_PASSWORD', 'guest')

# reserved users
reserved_users_regex = os.getenv('RESERVED_USERS_REGEX', None)
reserved_users_message = os.getenv('RESERVED_USERS_MESSAGE', None)

# PulseGuardian
warn_queue_size = int(os.getenv('WARN_QUEUE_SIZE', 2000))
del_queue_size = int(os.getenv('DEL_QUEUE_SIZE', 8000))
polling_interval = int(os.getenv('POLLING_INTERVAL', 5))
polling_max_interval = int(os.getenv('POLLING_MAX_INTERVAL', 300))
fake_account = os.getenv('FAKE_ACCOUNT', None)

# Only used if at least one log path is specified above.
max_log_size = int(os.getenv('MAX_LOG_SIZE', 20480))
backup_count = int(os.getenv('BACKUP_COUNT', 5))
