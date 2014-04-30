from flask import Flask, render_template
from model.base import db_session, init_db

app = Flask(__name__)
init_db()

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/signup", methods=['POST'])
def signup():
    return render_template('signup.html')



@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == "__main__":
    app.run()