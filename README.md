# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More information on [the wiki](https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian).

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python (2.7.x)
* pip (to install external dependencies)
* MySQL (if you're using the sqlalchemy MySQL engine, see below)

## Setup

* Clone the repository and cd into it
* Create and activate a virtualenv:
```
  virtualenv venv
  source venv/bin/activate
```
* Install the requirements:
```
  pip install -r requirements.txt
```
* Copy `src/config.py.example` to `src/config.py` and update it with the correct settings (database, email password, etc.)

## Usage

Make sure `rabbitmq-server` is running before you run the following commands.

**WARNING:**  the tests will mess with your local rabbitmq instance (wiping out existing queues, possibly deleting users) so make sure you don't run the tests on a production instance.

* Initialize the db with: `python src/dbinit.py`. *WARNING:* this removes any existing data the app might have previously stored in the databse.
* Optional: Generate some dummy data (dummy user account, admin account): `python src/dbinit.py --dummy`
* Run the Pulse Guardian daemon with: `python src/guardian.py`
* Run the web app (for development) with: `python src/web.py`
* For production, the web app can be run with [gunicorn](https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx) and such.
* Run tests with: `python src/runtests.py`
