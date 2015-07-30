import os

# Web app
flask_host = os.getenv('FLASK_HOST', 'localhost')
flask_port = int(os.getenv('FLASK_PORT', 5000))
flask_secret_key = os.getenv('FLASK_SECRET_KEY', None)
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

# Database
sqlalchemy_engine_url = os.getenv('SQLALCHEMY_ENGINE_URL',
                                  'mysql://root@localhost/pulseguardian')
pool_recycle_interval = int(os.getenv('POOL_RECYCLE_INTERVAL', 60))

# RabbitMQ
rabbit_host = os.getenv('RABBIT_HOST', 'localhost')
rabbit_management_port = int(os.getenv('RABBIT_MANAGEMENT_PORT', 15672))
rabbit_vhost = os.getenv('RABBIT_VHOST', '/')
rabbit_user = os.getenv('RABBIT_USER', 'guest')
rabbit_password = os.getenv('RABBIT_PASSWORD', 'guest')

# PulseGuardian
warn_queue_size = int(os.getenv('WARN_QUEUE_SIZE', 2000))
del_queue_size = int(os.getenv('DEL_QUEUE_SIZE', 8000))
polling_interval = int(os.getenv('POLLING_INTERVAL', 5))

# Logging
GUARDIAN_LOG_PATH = os.getenv('GUARDIAN_LOG_PATH', 'log_guardian.log')
WEBAPP_LOG_PATH = os.getenv('WEBAPP_LOG_PATH', 'log_web_guardian.log')
MAX_LOG_SIZE = int(os.getenv('MAX_LOG_SIZE', 20480))
BACKUP_COUNT = int(os.getenv('BACKUP_COUNT', 5))
DEBUG = bool(int(os.getenv('DEBUG', 0)))
