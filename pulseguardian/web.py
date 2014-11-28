# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import logging.handlers
import os.path
import re
import sys
from functools import wraps

import requests
import sqlalchemy.orm.exc
import werkzeug.serving
from flask import Flask, render_template, session, g, redirect, request, jsonify

import config
from model.base import db_session, init_db
from model.pulse_user import PulseUser
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException

# Development cert/key base filename.
DEV_CERT_BASE = 'dev'

# Monkey-patch werkzeug.

def generate_adhoc_ssl_pair(cn=None):
    """Generate a 1024-bit self-signed SSL pair.
    This is a verbatim copy of werkzeug.serving.generate_adhoc_ssl_pair
    from commit 91ec97963c77188cc75ba19b66e1ba0929376a34 except the key
    length has been increased from 768 bits to 1024 bits, since recent
    versions of Firefox and other browsers have increased key-length
    requirements.
    """
    from random import random
    from OpenSSL import crypto

    # pretty damn sure that this is not actually accepted by anyone
    if cn is None:
        cn = '*'

    cert = crypto.X509()
    cert.set_serial_number(int(random() * sys.maxint))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60 * 60 * 24 * 365)

    subject = cert.get_subject()
    subject.CN = cn
    subject.O = 'Dummy Certificate'

    issuer = cert.get_issuer()
    issuer.CN = 'Untrusted Authority'
    issuer.O = 'Self-Signed'

    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, 1024)
    cert.set_pubkey(pkey)
    cert.sign(pkey, 'md5')

    return cert, pkey

# This is used by werkzeug.serving.make_ssl_devcert().
werkzeug.serving.generate_adhoc_ssl_pair = generate_adhoc_ssl_pair


# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.flask_secret_key
app.config['SESSION_COOKIE_SECURE'] = True

# Setting up the web app's logger
file_handler = logging.handlers.RotatingFileHandler(
    config.WEBAPP_LOG_PATH, mode='a+',
    maxBytes=config.MAX_LOG_SIZE,
    backupCount=config.BACKUP_COUNT)

formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s",
                              "%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)

app.logger.addHandler(file_handler)

# Setting root logger
logging.getLogger().addHandler(file_handler)

if config.DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)

# Initializing the rabbitmq management API
pulse_management = PulseManagementAPI(host=config.rabbit_host,
                                      user=config.rabbit_user,
                                      password=config.rabbit_password)

# Initializing the databse
init_db()

# Fake account
fake_account = None

# Decorators and instructions used to inject info into the context or
# restrict access to some pages


def load_fake_account(fake_account):
    """Load fake user and setup session."""

    # Set session user.
    session['email'] = fake_account
    session['fake_account'] = True

    # Check if user already exists in the database, creating it if not.
    g.user = User.query.filter(User.email == fake_account).first()
    if g.user is None:
        g.user = User.new_user(email=fake_account)


def requires_login(f):
    """Decorator for views that require the user to be logged-in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('email') is None:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user():
    """Injects a user and configuration in templates' context."""
    cur_user = User.query.filter(User.email == session.get('email')).first()
    if cur_user and cur_user.pulse_users:
        pulse_user = cur_user.pulse_users[0]
    else:
        pulse_user = None
    return dict(cur_user=cur_user, pulse_user=pulse_user, config=config,
                session=session)


@app.before_request
def load_user():
    """Loads the currently logged-in user (if any) to the request context."""

    # Check if fake account is set and load user.
    if fake_account:
        load_fake_account(fake_account)
        return

    email = session.get('email')
    if not email:
        g.user = None
        return

    g.user = User.query.filter(User.email == session.get('email')).first()
    if not g.user:
        g.user = User.new_user(email=email)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Views

@app.route('/')
def index():
    if session.get('email'):
        if g.user.pulse_users:
            return redirect('/profile')
        return redirect('/register')
    return render_template('index.html')


@app.route('/register')
@requires_login
def register():
    return render_template('register.html', email=session.get('email'))


@app.route('/profile')
@requires_login
def profile(error=None, messages=None):
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('profile.html', users=users,
                           no_owner_queues=no_owner_queues,
                           error=error, messages=messages)


@app.route('/queues')
@requires_login
def queues():
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('queues.html', users=users,
                           no_owner_queues=no_owner_queues)


# API

@app.route('/queue/<path:queue_name>', methods=['DELETE'])
@requires_login
def delete_queue(queue_name):
    queue = Queue.query.get(queue_name)

    if queue and (g.user.admin or
                  (queue.owner and queue.owner.owner == g.user)):
        try:
            pulse_management.delete_queue(vhost='/', queue=queue.name)
        except PulseManagementException as e:
            logging.warning("Couldn't delete the queue '{0}' on "
                               "rabbitmq: {1}".format(queue_name, e))
            return jsonify(ok=False)
        db_session.delete(queue)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


@app.route('/pulse-user/<pulse_username>', methods=['DELETE'])
@requires_login
def delete_pulse_user(pulse_username):
    logging.info('Request to delete Pulse user "{0}".'.format(pulse_username))
    pulse_user = PulseUser.query.filter(PulseUser.username == pulse_username).first()

    if pulse_user and (g.user.admin or pulse_user.owner == g.user):
        try:
            pulse_management.delete_user(pulse_user.username)
        except PulseManagementException as e:
            logging.warning("Couldn't delete user '{0}' on "
                               "rabbitmq: {1}".format(pulse_username, e))
            return jsonify(ok=False)
        logging.info('Pulse user "{0}" deleted.'.format(pulse_username))
        db_session.delete(pulse_user)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


# Authentication related

@app.route('/auth/login', methods=['POST'])
def auth_handler():
    # The request has to have an assertion for us to verify
    if 'assertion' not in request.form:
        return jsonify(ok=False, message="Assertion parameter missing")

    # Send the assertion to Mozilla's verifier service.
    data = dict(assertion=request.form['assertion'],
                audience=config.persona_audience)
    resp = requests.post(config.persona_verifier, data=data, verify=True)

    # Did the verifier respond?
    if resp.ok:
        # Parse the response
        verification_data = resp.json()
        if verification_data['status'] == 'okay':
            email = verification_data['email']
            session['email'] = email

            user = User.query.filter(User.email == email).first()
            if user is None:
                user = User.new_user(email=email)

            if user.pulse_users:
                return jsonify(ok=True, redirect='/')

            return jsonify(ok=True, redirect='/register')

    # Oops, something failed. Abort.
    error_msg = "Couldn't connect to the Persona verifier ({0})".format(
        config.persona_verifier)
    logging.error(error_msg)
    return jsonify(ok=False, message=error_msg)


@app.route("/update_info", methods=['POST'])
@requires_login
def update_info():
    pulse_username = request.form['pulse-user']
    new_password = request.form['new-password']
    password_verification = request.form['new-password-verification']

    try:
        pulse_user = PulseUser.query.filter(
            PulseUser.username == pulse_username).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return profile(messages=["Invalid user."])

    if pulse_user.owner != g.user:
        return profile(messages=["Invalid user."])

    if not new_password:
        return profile(messages=["You didn't enter a new password."])

    if new_password != password_verification:
        return profile(error="Password verification doesn't match the "
                       "password.")

    if not PulseUser.strong_password(new_password):
        return profile(error="Your password must contain a mix of "
                       "letters and numerical characters and be at "
                       "least 6 characters long.")

    pulse_user.change_password(new_password, pulse_management)
    return profile(messages=["Password updated for user {0}.".format(
                pulse_username)])


@app.route('/register', methods=['POST'])
def register_handler():
    username = request.form['username']
    password = request.form['password']
    password_verification = request.form['password-verification']
    email = session['email']
    errors = []

    if password != password_verification:
        errors.append("Password verification doesn't match the password.")
    elif not PulseUser.strong_password(password):
        errors.append("Your password must contain a mix of letters and "
                      "numerical characters and be at least 6 characters long.")

    if not re.match('^[a-zA-Z][a-zA-Z0-9._-]*$', username):
        errors.append("The submitted username must start with an "
                      "alphabetical character and contain only alphanumeric "
                      "characters, periods, underscores, and hyphens.")

    # Checking if a user exists in RabbitMQ OR in our db
    try:
        user_response = pulse_management.user(username=username)
        in_rabbitmq = True
    except PulseManagementException:
        in_rabbitmq = False
    else:
        if 'error' in user_response:
            in_rabbitmq = False

    if (in_rabbitmq or
        PulseUser.query.filter(PulseUser.username == username).first()):
        errors.append("A user with the same username already exists.")

    if errors:
        return render_template('register.html', email=email,
                               signup_errors=errors)

    PulseUser.new_user(username, password, g.user, pulse_management)

    return redirect('/profile')


@app.route('/auth/logout', methods=['POST'])
def logout_handler():
    session['email'] = None
    return jsonify(ok=True, redirect='/')

@app.route('/quickstart')
def quickstart():    
    return render_template('quickstart.html')

def cli(args):
    """Process command line arguments and do some setup."""
    global fake_account

    # Add StreamHandler for development purposes
    logging.getLogger().addHandler(logging.StreamHandler())

    # Process command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('--fake-account', help='Email for fake dev account',
                        default=None)
    args = parser.parse_args(args)

    # If fake account is provided we need to do some setup
    if args.fake_account:
        ssl_context = None
        fake_account = args.fake_account
        app.config['SESSION_COOKIE_SECURE'] = False
    else:
        dev_cert = '%s.crt' % DEV_CERT_BASE
        dev_cert_key = '%s.key' % DEV_CERT_BASE
        if not os.path.exists(dev_cert) or not os.path.exists(dev_cert_key):
            logging.info('Creating dev certificate and key.')
            werkzeug.serving.make_ssl_devcert(DEV_CERT_BASE, host='localhost')
        ssl_context = (dev_cert, dev_cert_key)

    app.run(host=config.flask_host,
            port=config.flask_port,
            debug=config.flask_debug_mode,
            ssl_context=ssl_context)


if __name__ == "__main__":
    cli(sys.argv[1:])
