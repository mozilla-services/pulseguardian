#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import wraps

from flask import Flask, render_template, session, g, redirect, request

app = Flask(__name__)

from model.base import db_session, init_db
from model.user import User

import config

# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.secret_key
init_db()

# Dummy test user
if User.query.filter(User.email == 'dummy@email.com').first() is None:
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
    """ Injects the current logged-in user (if any) to the request context """
    if session.get('logged_in'):
        g.user = User.query.filter(User.email == session['logged_in']).first()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Views

@app.route("/")
def index():
    return render_template('index.html')

# Login / Signup

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