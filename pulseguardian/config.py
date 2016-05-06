import base64
import os

# Web app
flask_host = os.getenv('FLASK_HOST', 'localhost')
flask_port = int(os.getenv('FLASK_PORT', 5000))

try:
    flask_secret_key = base64.b64decode(os.getenv('FLASK_SECRET_KEY', None))
except TypeError:
    raise Exception('FLASK_SECRET_KEY must be base64 encoded.')

flask_debug_mode = bool(int(os.getenv('FLASK_DEBUG_MODE', 1)))

# Persona
persona_verifier = os.getenv('PERSONA_VERIFIER',
                             'https://verifier.login.persona.org/verify')
persona_audience = os.getenv('PERSONA_AUDIENCE',
                             'https://{0}:{1}'.format(flask_host, flask_port))

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

# PulseGuardian
warn_queue_size = int(os.getenv('WARN_QUEUE_SIZE', 2000))
del_queue_size = int(os.getenv('DEL_QUEUE_SIZE', 8000))
polling_interval = int(os.getenv('POLLING_INTERVAL', 5))
fake_account = os.getenv('FAKE_ACCOUNT', None)

# Logging
guardian_log_path = os.getenv('GUARDIAN_LOG_PATH', None)
webapp_log_path = os.getenv('WEBAPP_LOG_PATH', None)
debug_logs = bool(int(os.getenv('DEBUG', 0)))

# Only used if at least one log path is specified above.
max_log_size = int(os.getenv('MAX_LOG_SIZE', 20480))
backup_count = int(os.getenv('BACKUP_COUNT', 5))
