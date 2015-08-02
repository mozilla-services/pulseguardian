# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More
information on [the wiki][].

[![Build Status](https://travis-ci.org/mozilla/pulseguardian.svg?branch=master)](https://travis-ci.org/mozilla/pulseguardian)

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python (2.6+)
 * Python 2.6 **must** be supported
* pip (to install external dependencies)
* PostgreSQL (for production; testing environments can use sqlite)

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

* Set environment variables as necessary for your local settings.  See
  `pulseguardian/config.py`.

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

The fake account option will make development easier. This feature will
disable HTTPS and bypass Persona for testing. It will also create the
given user, if necessary, and log in automatically.

## Testing

PulseGuardian uses docker to run its test suite. Please follow the
[docker installation docs][] on how to install it in your system.

If you're installing on OS X, you'll be using `boot2docker`. During
initialization, you'll prompted to set some environment variables. Don't forget
to set them; that way the test suite will be able to pick up your docker host.

The docker container container will forward ports 5673 and 15673. Please be
sure that those ports are available.

Since PulseGuardian is configured via environment variables, you must ensure
that you have a clean environment before running the tests, i.e., no
PulseGuardian environment variables set. (FIXME: set up a full test environment
from within runtests.py rather than relying on defaults.)

The docker daemon must always run as the root user, but you need to be able to
run docker client commands without `sudo`. To achieve that you can:

* Add the docker group if it doesn't already exist:  `sudo groupadd docker`

* Add the connected user "${USER}" to the docker group. Change the user name
to match your preferred user:  `sudo gpasswd -a ${USER} docker`

* Restart the Docker daemon:  `sudo service docker restart`

* You need to log out and log back in again if you added the currently logged-in
user.

Finally, you can run tests with (from your project root folder):
`python test/runtests.py`.

If you prefer, you can run the tests against a local RabbitMQ installation. For
that you can run: `python test/runtests.py --use-local`.

**WARNING**: If you use your local RabbitMQ instance the tests will mess with it
(wiping out existing queues, possibly deleting users) so make sure you don't
run the tests on a production instance.

[the wiki]: https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian
[HACKING.md]: https://hg.mozilla.org/automation/mozillapulse/file/tip/HACKING.md
[Travis CI]: https://travis-ci.org/mozilla/pulseguardian
[gunicorn]: https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx
[docker installation docs]: https://docs.docker.com/installation/#installation
