# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More
information on [the wiki][].

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python (2.6+)
 * Python 2.6 **must** be supported
* pip (to install external dependencies)
* MySQL (if you're using the sqlalchemy MySQL engine, see below)

## Setup

See the mozillapulse [HACKING.md][] file for instructions on setting
up a local Pulse environment.

Using a virtualenv is highly recommended. One possible installation would be

* Clone the repository and cd into it.
* Create and activate a virtualenv:

  ```
    virtualenv venv
    source venv/bin/activate
  ```

Within the chosen environment, install and configure PulseGuardian:

* Install the requirements:

  ```
    pip install -r requirements.txt
  ```

* Copy `pulseguardian/config.py.example` to `pulseguardian/config.py` and
  update it with the correct settings (database, email password, etc.)

Because Persona requires an https connection, if you are running the
development server without the --fake-account option (see below), you
will also need the pyOpenSSL package.

Due to a bug in pyOpenSSL, development under Python 2.6 currently
requires unreleased code:

    pip install -e git+git://github.com/pyca/pyopenssl#egg=PyOpenSSL

Python 2.7 can use released versions:

    pip install pyOpenSSL

Note that, due to deployment logistics, PulseGuardian **must** run under
Python 2.6. Feel free to develop under 2.7, but don't use any
2.7-specific features, and try to test under 2.6 before submitting a
patch.

## Usage

Make sure `rabbitmq-server` is running and you're inside the source directory
(`pulseguardian`) before you run the following commands.

**WARNING**: The tests will mess with your local rabbitmq instance (wiping out
existing queues, possibly deleting users) so make sure you don't run the tests
on a production instance. (TODO: Support a docker/vagrant image (bug 1089457))

Note that tests are run on [Travis CI][]. Before submitting a patch,
it is highly recommended that you get a Travis CI account and
activate it on a GitHub fork of the pulseguardian repo. That way the
reviewer can quickly verify that all tests still pass with your changes.

* Initialize the db with: `python dbinit.py`. *WARNING*: This removes any
  existing data the app might have previously stored in the databse.
* Optional: Generate some dummy data (dummy user account, admin account):
  `python dbinit.py --dummy`
* Run the Pulse Guardian daemon with: `python guardian.py`
* Run the web app (for development) with:
  `python web.py --fake-account fake@email.com`
* For production, the web app can be run with [gunicorn][] and such.
* Run tests with: `python runtests.py`

The fake account option will make development easier. This feature will
disable HTTPS and bypass Persona for testing. It will also create the
given user, if necessary, and log in automatically.

[the wiki]: https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian
[HACKING.md]: https://hg.mozilla.org/automation/mozillapulse/file/tip/HACKING.md
[Travis CI]: https://travis-ci.org/mozilla/pulseguardian
[gunicorn]: https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx
