# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging
import logging.handlers
import re
from functools import wraps

from flask import Flask, render_template, session, g, redirect, request, jsonify
import requests

from model.base import db_session, init_db
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException
import config

# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.flask_secret_key
app.config['SESSION_COOKIE_SECURE'] = True

# Setting up the web app's logger
file_handler = logging.handlers.RotatingFileHandler(config.WEBAPP_LOG_PATH, mode='a+',
                                                    maxBytes=config.MAX_LOG_SIZE)
file_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)

app.logger.addHandler(file_handler)


# Initializing the rabbitmq management API
pulse_management = PulseManagementAPI(host=config.rabbit_host,
                                      user=config.rabbit_user,
                                      password=config.rabbit_password)

# Initializing the databse
init_db()


# Decorators and instructions used to inject info into the context or
# restrict access to some pages


def requires_login(f):
    """Decorator for views that require the user to be logged-in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('email') is None:
            return redirect('/')
        elif g.user is None:
            return redirect('/register')
        else:
            return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user():
    """Injects a user and configuration in templates' context."""
    cur_user = User.query.filter(User.email == session.get('email')).first()
    return dict(cur_user=cur_user, config=config, session=session)


@app.before_request
def load_user():
    """Loads the currently logged-in user (if any) to the request context."""
    g.user = User.query.filter(User.email == session.get('email')).first()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Views

@app.route('/')
def index():
    if session.get('email') and g.user is None:
        return redirect('/register')

    if g.user is not None:
        return redirect('/profile')

    return render_template('index.html')


@app.route('/quickstart')
def quickstart():
    return render_template('quickstart.html')

@app.route('/msgformat')
def msgformat():
    return render_template('msgformat.html')


@app.route('/register')
def register():
    if not (session.get('email') and g.user is None):
        return redirect('/')
    return render_template('register.html', email=session.get('email'))


@app.route('/profile')
@requires_login
def profile(error=None, messages=None):
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('profile.html', users=users, no_owner_queues=no_owner_queues,
                           error=error, messages=messages)


@app.route('/queues')
@requires_login
def queues():
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('queues.html', users=users, no_owner_queues=no_owner_queues)


# API

@app.route('/queue/<queue_name>', methods=['DELETE'])
def delete_queue(queue_name):
    queue = Queue.query.get(queue_name)

    if queue and g.user and queue.owner == g.user or g.user.admin:
        db_session.delete(queue)
        db_session.commit()
        try:
            pulse_management.delete_queue(vhost='/', queue=queue.name)
            return jsonify(ok=True)
        except PulseManagementException as e:
            app.logger.warning(
                "Couldn't delete the queue '{0}' on rabbitmq: {1}".format(queue_name, e))

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
                return jsonify(ok=True, redirect='/register')
            else:
                return jsonify(ok=True, redirect='/')

    # Oops, something failed. Abort.
    error_msg = "Couldn't connect to the Persona verifier ({0})".format(config.persona_verifier)
    app.logger.error(error_msg)
    return jsonify(ok=False, message=error_msg)

@app.route("/update_info", methods=['POST'])
@requires_login
def update_info():
    current_password = request.form['current-password']
    new_password = request.form['new-password']
    password_verification = request.form['new-password-verification']

    if new_password:
        if not g.user.valid_password(current_password):
            return profile(error="The given current password isn't valid.")
        elif new_password != password_verification:
            return profile(error="Password verification doesn't match the password.")
        elif not User.strong_password(new_password):
            return profile(error="Your password must contain a mix of letters and numerical characters and be at least 6 characters long")
        else:
            g.user.change_password(new_password, pulse_management)
            return profile(messages=["Correctly updated your password."])
    else:
        return profile(messages=["You didn't enter a new password."])

@app.route('/register', methods=['POST'])
def register_handler():
    username = request.form['username']
    password = request.form['password']
    email = session['email']
    errors = []

    if not re.match('^[a-z0-9]+$', username):
        errors.append("The submitted username contains non-alphanumeric characters")
    if User.query.filter(User.email == email).first():
        errors.append("A user with the same email already exists")
    if not User.strong_password(password):
        errors.append("Your password must contain a mix of letters and numerical characters and be at least 6 characters long")

    # Checking if a user exists in RabbitMQ OR in our db
    try:
        pulse_management.user(username=username)
        in_rabbitmq = True
    except PulseManagementException:
        in_rabbitmq = False

    if in_rabbitmq:
        errors.append("A user with the same username already exists in Pulse")
    if User.query.filter(User.username == username).first():
        errors.append("A user with the same username already exists in our database")
    if errors:
        signup_error = "{0}.".format(', '.join(errors))
        return render_template('register.html', email=email, signup_error=signup_error)

    user = User.new_user(email=email, username=username, password=password, management_api=pulse_management)
    db_session.add(user)
    db_session.commit()

    return render_template('confirm.html')

@app.route('/auth/logout', methods=['POST'])
def logout_handler():
    session['email'] = None
    return jsonify(ok=True, redirect='/')


if __name__ == "__main__":
    app.run(host=config.flask_host,
            port=config.flask_port,
            debug=config.flask_debug_mode,
            ssl_context='adhoc')
