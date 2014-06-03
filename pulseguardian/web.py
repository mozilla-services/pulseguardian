# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functools import wraps

from flask import Flask, render_template, session, g, redirect, request, jsonify, abort
import requests

from model.base import db_session, init_db
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException
from sendemail import sendemail
import config

# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.flask_secret_key

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
    user = User.query.filter(User.email == session.get('email')).first()
    return dict(cur_user=user, config=config, session=session)


@app.before_request
def load_user():
    """Loads the currently logged-in user (if any) to the request context."""
    g.user = User.query.filter(User.email == session.get('email')).first()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Views


@app.route("/")
def index():
    if g.user:
        return redirect('/profile')
    else:
        return render_template('index.html')


@app.route('/register')
def register():
    if session.get('email') is None:
        return redirect('/')
    return render_template('register.html', email=session.get('email'))

@app.route("/profile")
@requires_login
def profile():
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('profile.html', users=users, no_owner_queues=no_owner_queues)


@app.route("/queues")
@requires_login
def queues():
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('queues.html', users=users, no_owner_queues=no_owner_queues)


# API

@app.route("/queue/<queue_name>", methods=['DELETE'])
def delete_queue(queue_name):
    queue = Queue.query.get(queue_name)

    if queue and g.user and queue.owner == g.user or g.user.admin:
        db_session.delete(queue)
        db_session.commit()
        try:
            pulse_management.delete_queue(vhost='/', queue=queue.name)
            return jsonify(ok=True)
        except PulseManagementException:
            app.logger.warning(
                "Couldn't delete the queue '{}' on rabbitmq".format(queue_name))

    return jsonify(ok=False)


# Authentication related

def send_activation_email(user):
    # Sending the activation email
    activation_link = 'http://{}:{}/activate/{}/{}'.format(config.flask_host, config.flask_port,
                                                           user.email, user.activation_token)
    sendemail(
        subject="Activate your Pulse account", from_addr=config.email_from, to_addrs=[user.email],
        username=config.email_account, password=config.email_password,
        html_data=render_template('activation_email.html', user=user, activation_link=activation_link))


@app.route('/auth/login', methods=['POST'])
def auth_handler():
    # The request has to have an assertion for us to verify
    if 'assertion' not in request.form:
        abort(400)

    # Send the assertion to Mozilla's verifier service.
    data = dict(assertion=request.form['assertion'],
                audience='http://{}:{}'.format(config.flask_host, config.flask_port))
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
    abort(500)


@app.route('/register', methods=['POST'])
def register_handler():
    username = request.form['username']
    password = request.form['password']
    email = session['email']
    errors = []

    if User.query.filter(User.email == email).first():
        errors.append("A user with the same email already exists")

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
        signup_error = "{}.".format(', '.join(errors))
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
            debug=config.flask_debug_mode)
