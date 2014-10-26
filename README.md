# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More
information on [the wiki][].

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python (2.6+)
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
* Copy `pulseguardian/config.py.example` to `pulseguardian/config.py` and
  update it with the correct settings (database, email password, etc.)

## Usage

Make sure `rabbitmq-server` is running and you're inside the source directory
(`pulseguardian`) before you run the following commands.

**WARNING**: The tests will mess with your local rabbitmq instance (wiping out
existing queues, possibly deleting users) so make sure you don't run the tests
on a production instance.

* Initialize the db with: `python dbinit.py`. *WARNING*: This removes any
  existing data the app might have previously stored in the databse.
* Optional: Generate some dummy data (dummy user account, admin account):
  `python dbinit.py --dummy`
* Run the Pulse Guardian daemon with: `python guardian.py`
* Run the web app (for development) with:
    * `python web.py --fake-account fake@email.com`
* For production, the web app can be run with [gunicorn][] and such.
* Run tests with: `python runtests.py`

The fake account option will make development easier. This feature will
disable HTTPS and bypass Persona for testing. It will also create the
given user, if necessary, and log in automatically.

[the wiki]: https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian
[gunicorn]: https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx
