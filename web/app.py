#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import wraps

from flask import Flask, render_template, session, g, redirect, request

from model.base import db_session, init_db
from model.user import User

import config

# Initializing the web app and the database
app = Flask(__name__)
app.secret_key = config.secret_key
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
    """ Injects the current logged-in user (if any) to the request context """
    if session.get('logged_in'):
        g.user = User.query.filter(User.email == session['logged_in']).first()

# Views

@app.route("/")
def index():
    return render_template('index.html')

# Login / Signup

@app.route("/signup", methods=['POST'])
def signup():
    return render_template('signup.html')

@app.route("/login", methods=['POST'])
def login():
    email, password = request.args['email'], request.args['password']
    user = User.query.filter(User.email == email)
    if user.valid_password(password):
        session['logged_in'] = email
        return redirect('/')
    else:
        return redirect('/login')

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == "__main__":
    app.run(debug=True)