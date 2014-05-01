#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import wraps

from flask import Flask, render_template, session, g, redirect, request

app = Flask(__name__)

import config
from model.base import db_session, init_db, clear_db
from model.user import User

from sendemail import sendemail

# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.secret_key

# Clearing the database from old data
clear_db()
# Initializing the databse
init_db()
# Dummy test user
dummy_usr = User.new_user(email='dummy@email.com', username='dummy', password='dummypassword')
db_session.add(dummy_usr)
db_session.commit()

# Decorators and instructions used to inject info into the context or restrict access to some pages
def requires_login(f):
    """  Decorator for views that requires the user to be logged-in """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in', None):
            return redirect('/login')
        else:
            return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """ Injects a 'user' variable in templates' context when a user is logged-in """
    if session.get('logged_in', None):
        return dict(user=User.query.filter(User.email == session['logged_in']).first())
    else:
        return dict(user=None)

@app.before_request
def load_user():
    """ Loads the currently logged-in user (if any) to the request context """
    if session.get('logged_in'):
        g.user = User.query.filter(User.email == session['logged_in']).first()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Views

@app.route("/")
def index():
    return render_template('index.html')

# Login / Signup / Activate user

@app.route("/signup", methods=['POST'])
def signup():
    email, username, password = request.form['email'], request.form['username'], request.form['password']

    if User.query.filter(User.email == email).first():
        return render_template('index.html', signup_error="A user with the same email already exists")

    if User.query.filter(User.username == username).first():
        return render_template('index.html', signup_error="A user with the same username already exists")

    user = User.new_user(email=email, username=username, password=password)
    db_session.add(user)
    db_session.commit()

    # Sending the activation email
    sendemail.sendemail(from_addr=config.email_from, to_addrs=[user.email], username=config.email_account,
                        password=config.email_password, html_data=render_template('activation_mail.html', user=user))
    return render_template('confirm.html')


@app.route("/activate/<email>/<activation_token>", methods=['POST'])
def activate(email, activation_token):
    user = User.query.filter(User.email == email).first()

    if user is None:
        return render_template('activate.html', error="No user with the given email")
    elif user.activated:
        return render_template('activate.html', error="Requested user is already activated")
    elif user.activation_token != activation_token:
        return render_template('activate.html', error="Wrong activation token")
    else:
        user.activated = True
        db_session.add(user)
        db_session.commit()
        
    # Send email here
    return render_template('confirm.html')

@app.route("/login", methods=['POST'])
def login():
    email, password = request.form['email'], request.form['password']
    user = User.query.filter(User.email == email).first()
    if user and user.valid_password(password):
        session['logged_in'] = email
        return redirect('/')
    else:
        return render_template('index.html', login_error="User doesn't exist or incorrect password")

@app.route("/logout", methods=['GET'])
def logout():
    del session['logged_in']
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)