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

import os

import sqlalchemy.orm.exc
import werkzeug.serving
from flask import (
    abort,
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_secure_headers.core import Secure_Headers
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from pulseguardian import auth, config, management as pulse_management, mozdef
from pulseguardian.model.base import db_session, init_db
from pulseguardian.model.pulse_user import RabbitMQAccount
from pulseguardian.model.queue import Queue
from pulseguardian.model.user import User

# Development cert/key base filename.
DEV_CERT_BASE = "dev"

# Role for admin user
ADMIN_ROLE = "admin"

# Initialize the web app.
app = Flask(__name__)
app.config["SERVER_NAME"] = config.flask_server_name
app.config["PREFERRED_URL_SCHEME"] = "https" if config.flask_use_ssl else "http"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.secret_key = config.flask_secret_key

# Handle HTTPS properly when running on Heroku dyno behind a proxy.
if "DYNO" in os.environ:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Load security headers.
sh = Secure_Headers()
sh.rewrite(
    {
        "CSP": {
            "connect-src": [
                "self",
            ],
            "img-src": [
                "self",
            ],
            "object-src": [
                "self",
            ],
            "script-src": [
                "self",
            ],
            "style-src": [
                "self",
            ],
        },
        "X-Permitted-Cross-Domain-Policies": None,
        "HPKP": None,
    }
)

# Log in with a fake account if set up.  This is an easy way to test
# without requiring authentication.
fake_account = None

if config.fake_account:
    fake_account = config.fake_account
    app.config["SESSION_COOKIE_SECURE"] = False
else:
    app.config["SESSION_COOKIE_SECURE"] = True

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
    if "_csrf_token" not in session:
        session["_csrf_token"] = base64.b64encode(os.urandom(24)).decode("ascii")
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def load_fake_account(fake_account):
    """Load fake user and setup session."""

    # Set session user.
    session["userinfo"] = {"email": fake_account}
    session["fake_account"] = True

    g.user = _load_user_from_email(fake_account)


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
    if not session.get("userinfo"):
        return None

    return User.get_by(email=session["userinfo"]["email"])


def _load_user_from_email(email):
    try:
        email = email.lower()
        user = User.get_by(email=email)

        if not user:
            user = User.new_user(email=email)

        return user
    except Exception as e:
        mozdef.log(
            mozdef.ERROR,
            mozdef.ACCOUNT_UPDATE,
            "Failed to load user account",
            details={"error": str(e), "email": email},
        )
        return None


@app.context_processor
def inject_user():
    """Injects a user and configuration in templates' context."""
    cur_user = current_user(session)

    if cur_user and cur_user.rabbitmq_accounts:
        rabbitmq_account = cur_user.rabbitmq_accounts[0]
    else:
        rabbitmq_account = None

    return dict(
        cur_user=cur_user,
        rabbitmq_account=rabbitmq_account,
        config=config,
        session=session,
    )


@app.before_request
def load_user():
    """Loads the currently logged-in user (if any) to the request context."""

    # Check if fake account is set and load user.
    if fake_account:
        load_fake_account(fake_account)
        return

    userinfo = session.get("userinfo")
    if not userinfo:
        g.user = None
        return

    g.user = _load_user_from_email(session["userinfo"]["email"])


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
    if app.config.get("TESTING"):
        return

    if not g._csrf_exempt:
        if request.method == "POST":
            page_csrf_token = request.form.get("_csrf_token")
        elif request.method == "DELETE":
            page_csrf_token = request.headers.get("X-CSRF-Token")
        else:
            return

        session_csrf_token = session.pop("_csrf_token", None)

        if not session_csrf_token or session_csrf_token != page_csrf_token:
            abort(400)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# Views


@app.route("/")
@sh.wrapper()
def index():
    if session.get("id_token"):
        if g.user.rabbitmq_accounts:
            return redirect("/rabbitmq_accounts")
        return redirect("/register")
    return render_template("index.html")


@app.route("/login")
@sh.wrapper()
def login():
    """Initiate OAuth login with Auth0."""
    redirect_uri = url_for("callback", _external=True)
    return authentication.oauth.auth0.authorize_redirect(redirect_uri)


@app.route("/redirect_uri")
@sh.wrapper()
def callback():
    """Handle OAuth callback from Auth0."""
    token = authentication.oauth.auth0.authorize_access_token()
    session["userinfo"] = token["userinfo"]
    session["id_token"] = token["id_token"]

    g.user = _load_user_from_email(session["userinfo"]["email"])

    if not g.user:
        return redirect("/login")

    if not g.user.rabbitmq_accounts:
        return redirect("/register")
    return redirect("/rabbitmq_accounts")


@app.route("/register")
@oidc.oidc_auth
@sh.wrapper()
def register(error=None):
    return render_template(
        "register.html", email=session["userinfo"]["email"], error=error
    )


@app.route("/rabbitmq_accounts")
@sh.wrapper()
@oidc.oidc_auth
def rabbitmq_accounts(error=None, messages=None):
    users = no_owner_queues = []
    if g.user.admin:
        users = User.get_all()
        no_owner_queues = list(
            db_session.execute(select(Queue).where(Queue.owner == None)).scalars()
        )
    return render_template(
        "rabbitmq_accounts.html",
        users=users,
        no_owner_queues=no_owner_queues,
        error=error,
        messages=messages,
    )


@app.route("/all_users")
@sh.wrapper()
@oidc.oidc_auth
@requires_admin
def all_users():
    users = User.get_all()
    return render_template("all_users.html", users=users)


@app.route("/all_rabbitmq_accounts")
@sh.wrapper()
@oidc.oidc_auth
def all_pulse_users():
    rabbitmq_accounts = (
        db_session.execute(
            select(RabbitMQAccount).options(joinedload(RabbitMQAccount.owners))
        )
        .unique()
        .scalars()
        .all()
    )
    return render_template(
        "all_rabbitmq_accounts.html", rabbitmq_accounts=rabbitmq_accounts
    )


@app.route("/queues")
@sh.wrapper()
@oidc.oidc_auth
def queues():
    if g.user.admin:
        users = User.get_all()
        no_owner_queues = list(
            db_session.execute(select(Queue).where(Queue.owner == None)).scalars()
        )
    else:
        users = [current_user(session)]
        no_owner_queues = []

    return render_template("queues.html", users=users, no_owner_queues=no_owner_queues)


@app.route("/queues_listing")
@sh.wrapper()
@oidc.oidc_auth
def queues_listing():
    if g.user.admin:
        users = User.get_all()
        no_owner_queues = list(
            db_session.execute(select(Queue).where(Queue.owner == None)).scalars()
        )
    else:
        users = [current_user(session)]
        no_owner_queues = []

    return render_template(
        "queues_listing.html", users=users, no_owner_queues=no_owner_queues
    )


# API


@app.route("/queue/<path:queue_name>", methods=["DELETE"])
@sh.wrapper()
@oidc.oidc_auth
def delete_queue(queue_name):
    queue = db_session.get(Queue, queue_name)

    if queue and (g.user.admin or (queue.owner and g.user in queue.owner.owners)):
        details = {
            "queuename": queue_name,
            "username": g.user.email,
        }

        try:
            pulse_management.delete_queue(vhost=config.rabbit_vhost, queue=queue.name)
        except pulse_management.PulseManagementException as e:
            details["message"] = str(e)
            mozdef.log(
                mozdef.ERROR,
                mozdef.OTHER,
                "Error deleting queue",
                details=details,
                tags=["queue"],
            )
            return jsonify(ok=False)

        mozdef.log(
            mozdef.NOTICE,
            mozdef.OTHER,
            "Deleting queue",
            details=details,
            tags=["queue"],
        )
        db_session.delete(queue)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


@app.route("/rabbitmq-account/<rabbitmq_username>", methods=["DELETE"])
@sh.wrapper()
@oidc.oidc_auth
def delete_rabbitmq_account(rabbitmq_username):
    rabbitmq_account = RabbitMQAccount.get_by(username=rabbitmq_username)

    if rabbitmq_account and (g.user.admin or g.user in rabbitmq_account.owners):
        details = {
            "username": g.user.email,
            "rabbitmqusername": rabbitmq_username,
        }
        try:
            pulse_management.delete_user(rabbitmq_account.username)
        except pulse_management.PulseManagementException as e:
            details["message"] = str(e)
            mozdef.log(
                mozdef.ERROR,
                mozdef.OTHER,
                "Error deleting RabbitMQ account",
                details=details,
            )
            return jsonify(ok=False)

        mozdef.log(
            mozdef.NOTICE,
            mozdef.OTHER,
            "RabbitMQ account deleted",
            details=details,
        )
        db_session.delete(rabbitmq_account)
        db_session.commit()
        return jsonify(ok=True)

    return jsonify(ok=False)


@app.route("/user/<user_id>/set-admin", methods=["PUT"])
@sh.wrapper()
@oidc.oidc_auth
@requires_admin
def set_user_admin(user_id):
    if "isAdmin" not in request.json:
        abort(400)

    user = db_session.get(User, int(user_id))
    if not user:
        abort(400)

    is_admin = request.json["isAdmin"]

    details = {
        "username": g.user.email,
        "newadminvalue": is_admin,
        "targetusername": user.email,
    }

    try:
        user.set_admin(is_admin)
        mozdef.log(
            mozdef.NOTICE,
            mozdef.ACCOUNT_UPDATE,
            "Admin role changed",
            details=details,
        )
    except Exception as e:
        details["message"] = str(e)
        mozdef.log(
            mozdef.ERROR,
            mozdef.ACCOUNT_UPDATE,
            "Admin role update failed.",
            details=details,
        )
        return jsonify(ok=False)

    return jsonify(ok=True)


# Read-Only API


@app.route("/contribute.json", methods=["GET"])
@sh.wrapper()
def contribute_json():
    return app.send_static_file("contribute.json")


@app.route("/queue/<path:queue_name>/bindings", methods=["GET"])
@sh.wrapper()
def bindings_listing(queue_name):
    queue = db_session.get(Queue, queue_name)
    bindings = []
    if queue:
        bindings = pulse_management.queue_bindings(
            vhost=config.rabbit_vhost, queue=queue.name
        )
    return jsonify({"queue_name": queue_name, "bindings": bindings})


@app.route("/update_info", methods=["POST"])
@sh.wrapper()
@oidc.oidc_auth
def update_info():
    rabbitmq_username = request.form["rabbitmq-username"]
    new_password = request.form["new-password"]
    password_verification = request.form["new-password-verification"]
    new_owners = _clean_owners_str(request.form["owners-list"])

    try:
        rabbitmq_account = db_session.execute(
            select(RabbitMQAccount).where(RabbitMQAccount.username == rabbitmq_username)
        ).scalar_one()
    except sqlalchemy.orm.exc.NoResultFound:
        return rabbitmq_accounts(
            messages=["RabbitMQ account {} not found.".format(rabbitmq_username)]
        )

    if g.user not in rabbitmq_account.owners:
        return rabbitmq_accounts(
            messages=["Invalid user: {} is not an owner.".format(g.user.email)]
        )

    messages = []
    error = None
    if new_password:
        if new_password != password_verification:
            return rabbitmq_accounts(
                error="Password verification doesn't match the password."
            )

        if not RabbitMQAccount.strong_password(new_password):
            return rabbitmq_accounts(
                error="Your password must contain a mix of letters and "
                "numerical characters and be at least 6 characters long."
            )

        rabbitmq_account.change_password(new_password)
        messages.append("Password updated for user {0}.".format(rabbitmq_username))

    # Update the owners list, if needed.
    old_owners = {user.email for user in rabbitmq_account.owners}
    if new_owners and new_owners != old_owners:
        # The list was changed.  Do an update.
        new_owner_users = list(
            db_session.execute(select(User).where(User.email.in_(new_owners))).scalars()
        )
        if new_owner_users:
            # At least some of the new owners are real users in the db.
            rabbitmq_account.owners = new_owner_users
            db_session.commit()

            updated_owners = {user.email for user in new_owner_users}
            invalid_owners = sorted(new_owners - updated_owners)
            if invalid_owners:
                error = "Some user emails not found: {}".format(
                    ", ".join(invalid_owners)
                )
            else:
                messages = ["Email list updated."]
        else:
            error = (
                "Invalid owners: "
                "Must be a comma-delimited list of existing user emails."
            )

    if not error and not messages:
        messages = ["No info updated."]

    return rabbitmq_accounts(messages=messages, error=error)


def _clean_owners_str(owners_str):
    """Turn a comma-delimited string of owner emails into a list.

    Though a one-liner, this ensures we're consistent with handling this
    email string.
    """
    return {owner.strip() for owner in owners_str.split(",") if owner}


@app.route("/register", methods=["POST"])
@sh.wrapper()
def register_handler():
    username = request.form["username"]
    password = request.form["password"]
    password_verification = request.form["password-verification"]
    owners = _clean_owners_str(request.form["owners-list"])
    email = session["userinfo"]["email"]
    errors = []

    if password != password_verification:
        errors.append("Password verification doesn't match the password.")
    elif not RabbitMQAccount.strong_password(password):
        errors.append(
            "Your password must contain a mix of letters and "
            "numerical characters and be at least 6 characters "
            "long."
        )

    if not re.match("^[a-zA-Z][a-zA-Z0-9._-]*$", username):
        errors.append(
            "The submitted username must start with an "
            "alphabetical character and contain only alphanumeric "
            "characters, periods, underscores, and hyphens."
        )

    if config.reserved_users_regex and re.match(config.reserved_users_regex, username):
        errors.append(
            "The submitted username is reserved. " + config.reserved_users_message
        )

    # Checking if a user exists in RabbitMQ OR in our db
    try:
        user_response = pulse_management.user(username=username)
        in_rabbitmq = True
    except pulse_management.PulseManagementException:
        in_rabbitmq = False
    else:
        if "error" in user_response:
            in_rabbitmq = False

    if in_rabbitmq or RabbitMQAccount.get_by(username=username):
        errors.append("An account with the same username already exists.")

    if errors:
        return render_template("register.html", email=email, signup_errors=errors)

    owner_users = list(
        db_session.execute(select(User).where(User.email.in_(owners))).scalars()
    )
    # Reject with error message if the owner list is unparse-able or contains
    # no users that actualy exist.
    if not owner_users:
        return register(
            error="Invalid owners list: {}".format(
                request.form["owners-list"] or "None"
            )
        )

    RabbitMQAccount.new_user(username, password, owner_users)

    return redirect("/rabbitmq_accounts")


@app.route("/auth/logout", methods=["POST"])
@sh.wrapper()
@oidc.oidc_logout
def logout_handler():
    return redirect("/")


@app.route("/whats_pulse")
@sh.wrapper()
def why():
    return render_template("index.html")


def cli(args):
    """Command-line handler.

    Since moving to Heroku, it is preferable to set a .env file with
    environment variables and start up the system with 'foreman start'
    rather than executing web.py directly.
    """
    ssl_context = None

    if config.flask_use_ssl:
        dev_cert = "%s.crt" % DEV_CERT_BASE
        dev_cert_key = "%s.key" % DEV_CERT_BASE
        if not os.path.exists(dev_cert) or not os.path.exists(dev_cert_key):
            werkzeug.serving.make_ssl_devcert(DEV_CERT_BASE, host="localhost")
        ssl_context = (dev_cert, dev_cert_key)

    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug_mode,
        ssl_context=ssl_context,
    )


if __name__ == "__main__":
    cli(sys.argv[1:])
