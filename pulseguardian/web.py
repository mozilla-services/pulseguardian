# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# The CSRF protection code was adapted from
#     https://github.com/sjl/flask-csrf/blob/master/flaskext/csrf.py
#
# That code is under the following license:
# Copyright (c) 2010 Steve Losh

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


import base64
import os.path
import re
import sys
from functools import wraps

import sqlalchemy.orm.exc
import werkzeug.serving
from flask import (abort,
                   Flask,
                   g,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   session)
from flask_secure_headers.core import Secure_Headers
from flask_sslify import SSLify
from sqlalchemy.orm import joinedload
from werkzeug.routing import NotFound

from pulseguardian import auth, config, management as pulse_management, mozdef
from pulseguardian.model.base import db_session, init_db
from pulseguardian.model.pulse_user import PulseUser
from pulseguardian.model.queue import Queue
from pulseguardian.model.user import User

# Development cert/key base filename.
DEV_CERT_BASE = 'dev'

# Role for admin user
ADMIN_ROLE = 'admin'

# Initialize the web app.
app = Flask(__name__)
app.config['SERVER_NAME'] = config.flask_server_name
app.config['PREFERRED_URL_SCHEME'] = ('https' if config.flask_use_ssl
                                      else 'http')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.secret_key = config.flask_secret_key

# Redirect to https if running on Heroku dyno.
if 'DYNO' in os.environ:
    sslify = SSLify(app)

# Load security headers.
sh = Secure_Headers()
sh.rewrite({
    'CSP': {
        'connect-src': [
            'self',
        ],
        'img-src': [
            'self',
        ],
        'object-src': [
            'self',
        ],
        'script-src': [
            'self',
        ],
        'style-src': [
            'self',
        ],
    },
    'X-Permitted-Cross-Domain-Policies': None,
    'HPKP': None,
})

# Log in with a fake account if set up.  This is an easy way to test
# without requiring authentication.
fake_account = None

if config.fake_account:
    fake_account = config.fake_account
    app.config['SESSION_COOKIE_SECURE'] = False
else:
    app.config['SESSION_COOKIE_SECURE'] = True

authentication = auth.OpenIDConnect()
oidc = authentication.auth(app)

# Initialize the database.
init_db()


# Decorators and instructions used to inject info into the context or
# restrict access to some pages.

csrf_exempt_views = []


def csrf_exempt(view):
    csrf_exempt_views.append(view)
    return view


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = base64.b64encode(os.urandom(24))
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token


def load_fake_account(fake_account):
    """Load fake user and setup session."""

    # Set session user.
    session['userinfo'] = {'email': fake_account}
    session['fake_account'] = True

    # Check if user already exists in the database, creating it if not.
    g.user = User.query.filter(User.email == fake_account).first()
    if g.user is None:
        g.user = User.new_user(email=fake_account)


def requires_admin(f):
    """Decorator for views that are allowed for admin users only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user.admin:
            """404: Non admin user does not have access to this route."""
            abort(404)
        return f(*args, **kwargs)
    return decorated_function


def current_user(session):
    if not session.get('userinfo'):
        return None

    return User.query.filter(
        User.email == session['userinfo']['email']
    ).first()


@app.context_processor
def inject_user():
    """Injects a user and configuration in templates' context."""
    cur_user = current_user(session)

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

    userinfo = session.get('userinfo')
    if not userinfo:
        g.user = None
        return

    email = session['userinfo']['email']
    g.user = User.query.filter(User.email == email).first()

    if not g.user:
        g.user = User.new_user(email=email)


@app.before_request
def csrf_check_exemptions():
    try:
        dest = app.view_functions.get(request.endpoint)
        g._csrf_exempt = dest in csrf_exempt_views
    except NotFound:
        g._csrf_exempt = False


@app.before_request
def _csrf_protect():
    # This simplifies unit testing, wherein CSRF seems to break
    if app.config.get('TESTING'):
        return

    if not g._csrf_exempt:
        if request.method == "POST":
            page_csrf_token = request.form.get('_csrf_token')
        elif request.method == "DELETE":
            page_csrf_token = request.headers.get('X-CSRF-Token')
        else:
            return

        session_csrf_token = session.pop('_csrf_token', None)

        if not session_csrf_token or session_csrf_token != page_csrf_token:
            abort(400)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# Views

@app.route('/')
@sh.wrapper()
def index():
    if session.get('id_token'):
        if g.user.pulse_users:
            return redirect('/profile')
        return redirect('/register')
    return render_template('index.html')


@app.route('/register')
@oidc.oidc_auth
@sh.wrapper()
def register(error=None):
    return render_template('register.html', email=session['userinfo']['email'],
                           error=error)


@app.route('/profile')
@sh.wrapper()
@oidc.oidc_auth
def profile(error=None, messages=None):
    users = no_owner_queues = []
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    return render_template('profile.html', users=users,
                           no_owner_queues=no_owner_queues,
                           error=error, messages=messages)


@app.route('/all_users')
@sh.wrapper()
@oidc.oidc_auth
@requires_admin
def all_users():
    users = User.query.all()
    return render_template('all_users.html', users=users)


@app.route('/all_pulse_users')
@sh.wrapper()
@oidc.oidc_auth
def all_pulse_users():
    pulse_users = PulseUser.query.options(joinedload('owners'))
    return render_template('all_pulse_users.html', pulse_users=pulse_users)


@app.route('/queues')
@sh.wrapper()
@oidc.oidc_auth
def queues():
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    else:
        users = [current_user(session)]
        no_owner_queues = []

    return render_template('queues.html', users=users,
                           no_owner_queues=no_owner_queues)


@app.route('/queues_listing')
@sh.wrapper()
@oidc.oidc_auth
def queues_listing():
    if g.user.admin:
        users = User.query.all()
        no_owner_queues = list(Queue.query.filter(Queue.owner == None))
    else:
        users = [current_user(session)]
        no_owner_queues = []

    return render_template('queues_listing.html', users=users,
                           no_owner_queues=no_owner_queues)


# API

@app.route('/queue/<path:queue_name>', methods=['DELETE'])
@sh.wrapper()
@oidc.oidc_auth
def delete_queue(queue_name):
    queue = Queue.query.get(queue_name)

    if queue and (g.user.admin or
                  (queue.owner and g.user in queue.owner.owners)):
        details = {
            'queuename': queue_name,
            'username': g.user.email,
        }

        try:
            pulse_management.delete_queue(vhost='/', queue=queue.name)
        except pulse_management.PulseManagementException as e:
            details['message'] = str(e)
            mozdef.log(
                mozdef.ERROR,
                mozdef.OTHER,
                'Error deleting queue',
                details=details,
                tags=['queue'],
            )
            return jsonify(ok=False)

        mozdef.log(
            mozdef.NOTICE,
            mozdef.OTHER,
            'Deleting queue',
            details=details,
            tags=['queue'],
        )
        db_session.delete(queue)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


@app.route('/pulse-user/<pulse_username>', methods=['DELETE'])
@sh.wrapper()
@oidc.oidc_auth
def delete_pulse_user(pulse_username):
    pulse_user = PulseUser.query.filter(
        PulseUser.username == pulse_username).first()

    if pulse_user and (g.user.admin or g.user in pulse_user.owners):
        details = {
            'username': g.user.email,
            'pulseusername': pulse_username,
        }
        try:
            pulse_management.delete_user(pulse_user.username)
        except pulse_management.PulseManagementException as e:
            details['message'] = str(e)
            mozdef.log(
                mozdef.ERROR,
                mozdef.OTHER,
                'Error deleting RabbitMQ account',
                details=details,
            )
            return jsonify(ok=False)

        mozdef.log(
            mozdef.NOTICE,
            mozdef.OTHER,
            'RabbitMQ account deleted',
            details=details,
        )
        db_session.delete(pulse_user)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


@app.route('/user/<user_id>/set-admin', methods=['PUT'])
@sh.wrapper()
@oidc.oidc_auth
@requires_admin
def set_user_admin(user_id):
    if 'isAdmin' not in request.json:
        abort(400)

    user = User.query.get(user_id)
    if not user:
        abort(400)

    is_admin = request.json['isAdmin']

    details = {
        'username': g.user.email,
        'newadminvalue': is_admin,
        'targetusername': user.email,
    }

    try:
        user.set_admin(is_admin)
        mozdef.log(
            mozdef.NOTICE,
            mozdef.ACCOUNT_UPDATE,
            'Admin role changed',
            details=details,
        )
    except Exception as e:
        details['message'] = str(e)
        mozdef.log(
            mozdef.ERROR,
            mozdef.ACCOUNT_UPDATE,
            'Admin role update failed.',
            details=details
        )
        return jsonify(ok=False)

    return jsonify(ok=True)


# Read-Only API

@app.route('/contribute.json', methods=['GET'])
@sh.wrapper()
def contribute_json():
    return app.send_static_file('contribute.json')


@app.route('/queue/<path:queue_name>/bindings', methods=["GET"])
@sh.wrapper()
def bindings_listing(queue_name):
    queue = Queue.query.get(queue_name)
    bindings = []
    if queue:
        bindings = pulse_management.queue_bindings(vhost='/', queue=queue.name)
    return jsonify({"queue_name": queue_name, "bindings": bindings})


@app.route("/update_info", methods=['POST'])
@sh.wrapper()
@oidc.oidc_auth
def update_info():
    pulse_username = request.form['pulse-user']
    new_password = request.form['new-password']
    password_verification = request.form['new-password-verification']
    new_owners = _clean_owners_str(request.form['owners-list'])

    try:
        pulse_user = PulseUser.query.filter(
            PulseUser.username == pulse_username).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return profile(
            messages=["RabbitMQ account {} not found.".format(pulse_username)])

    if g.user not in pulse_user.owners:
        return profile(
            messages=[
                "Invalid user: {} is not an owner.".format(g.user.email)
            ]
        )

    messages = []
    error = None
    if new_password:
        if new_password != password_verification:
            return profile(error="Password verification doesn't match the "
                           "password.")

        if not PulseUser.strong_password(new_password):
            return profile(error="Your password must contain a mix of "
                           "letters and numerical characters and be at "
                           "least 6 characters long.")

        pulse_user.change_password(new_password)
        messages.append("Password updated for user {0}.".format(
                        pulse_username))

    # Update the owners list, if needed.
    old_owners = {user.email for user in pulse_user.owners}
    if new_owners and new_owners != old_owners:
        # The list was changed.  Do an update.
        new_owner_users = list(User.query.filter(User.email.in_(new_owners)))
        if new_owner_users:
            # At least some of the new owners are real users in the db.
            pulse_user.owners = new_owner_users
            db_session.commit()

            updated_owners = {user.email for user in new_owner_users}
            invalid_owners = sorted(new_owners - updated_owners)
            if invalid_owners:
                error = "Some user emails not found: {}".format(
                    ', '.join(invalid_owners))
            else:
                messages = ["Email list updated."]
        else:
            error = ("Invalid owners: "
                     "Must be a comma-delimited list of existing user emails.")

    if not error and not messages:
        messages = ["No info updated."]

    return profile(messages=messages, error=error)


def _clean_owners_str(owners_str):
    """Turn a comma-delimited string of owner emails into a list.

    Though a one-liner, this ensures we're consistent with handling this
    email string.
    """
    return {owner.strip() for owner in owners_str.split(",") if owner}


@app.route('/register', methods=['POST'])
@sh.wrapper()
def register_handler():
    username = request.form['username']
    password = request.form['password']
    password_verification = request.form['password-verification']
    owners = _clean_owners_str(request.form['owners-list'])
    email = session['userinfo']['email']
    errors = []

    if password != password_verification:
        errors.append("Password verification doesn't match the password.")
    elif not PulseUser.strong_password(password):
        errors.append("Your password must contain a mix of letters and "
                      "numerical characters and be at least 6 characters "
                      "long.")

    if not re.match('^[a-zA-Z][a-zA-Z0-9._-]*$', username):
        errors.append("The submitted username must start with an "
                      "alphabetical character and contain only alphanumeric "
                      "characters, periods, underscores, and hyphens.")

    if config.reserved_users_regex and re.match(config.reserved_users_regex,
                                                username):
        errors.append("The submitted username is reserved. "
                      + config.reserved_users_message)

    # Checking if a user exists in RabbitMQ OR in our db
    try:
        user_response = pulse_management.user(username=username)
        in_rabbitmq = True
    except pulse_management.PulseManagementException:
        in_rabbitmq = False
    else:
        if 'error' in user_response:
            in_rabbitmq = False

    if (in_rabbitmq or
            PulseUser.query.filter(PulseUser.username == username).first()):
        errors.append("An account with the same username already exists.")

    if errors:
        return render_template('register.html', email=email,
                               signup_errors=errors)

    owner_users = list(User.query.filter(User.email.in_(owners)))
    # Reject with error message if the owner list is unparse-able or contains
    # no users that actualy exist.
    if not owner_users:
        return register(error="Invalid owners list: {}".format(
            request.form['owners-list'] or "None"))

    PulseUser.new_user(username, password, owner_users)

    return redirect('/profile')


@app.route('/auth/logout', methods=['POST'])
@sh.wrapper()
@oidc.oidc_logout
def logout_handler():
    session['userinfo'] = None
    return redirect('/')


@app.route('/whats_pulse')
@sh.wrapper()
def why():
    return render_template('index.html')


def cli(args):
    """Command-line handler.

    Since moving to Heroku, it is preferable to set a .env file with
    environment variables and start up the system with 'foreman start'
    rather than executing web.py directly.
    """
    ssl_context = None

    if config.flask_use_ssl:
        dev_cert = '%s.crt' % DEV_CERT_BASE
        dev_cert_key = '%s.key' % DEV_CERT_BASE
        if not os.path.exists(dev_cert) or not os.path.exists(dev_cert_key):
            werkzeug.serving.make_ssl_devcert(DEV_CERT_BASE, host='localhost')
        ssl_context = (dev_cert, dev_cert_key)

    app.run(host=config.flask_host,
            port=config.flask_port,
            debug=config.flask_debug_mode,
            ssl_context=ssl_context)


if __name__ == "__main__":
    cli(sys.argv[1:])
