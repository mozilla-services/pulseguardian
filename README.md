# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More
information on [the wiki][].

[![Build Status](https://travis-ci.org/mozilla/pulseguardian.svg?branch=master)](https://travis-ci.org/mozilla/pulseguardian)

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python 2.7
* pip (to install external dependencies)
* PostgreSQL (for production; testing environments can use sqlite)

## Setup

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

Because Persona requires an https connection, if you are running the
development server without the `--fake-account` option (see below), you
will also need the pyOpenSSL package:

    pip install pyOpenSSL

You will also need a RabbitMQ instance running somewhere.  Docker provides a
lightweight and isolated solution.  See the [docker installation docs][] for
your system.

To create a Pulse Docker image, run this from within the `test` directory
(which contains the necessary `Dockerfile`):

    docker build -t="pulse:testing" test

When that finishes building, you can run a RabbitMQ instance in a Docker
container with

    docker run -d -p 5672:5672 -p 15672:15672 --name pulse pulse:testing

This will run RabbitMQ in a container in the background.  It will also forward
the AMQP and management API ports, 5672 and 15672, respectively, from the
container to your local host.

To stop the container, run

    docker stop pulse

You can remove the container with

    docker rm pulse

And you can remove the images with

    docker rmi pulse:testing
    docker rmi ubuntu:14.04

You can also use either a local RabbitMQ server or a VM.  See the
mozillapulse [HACKING.md][] file for instructions on setting up both of these.

Finally, you need your environment set up correctly.  If you are running
RabbitMQ in the Docker configuration described above, the defaults should
be mostly fine.  You will need to set `FLASK_SECRET_KEY` and probably
`DATABASE_URL`.  To use a random secret key and a local sqlite database named
`pulseguardian.db`, run the following from within the root PulseGuardian
source directory:

    export FLASK_SECRET_KEY=`python gen_secret_key.py`
    export DATABASE_URL=sqlite:///`pwd`/db

See the complete listing of options in `pulseguardian/config.py`.

TODO: Each of these options should be documented in the source.

## Usage

Make sure `rabbitmq-server` is running, your environment variables are
configured properly, and that you're inside the source directory
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

With docker installed and configured appropriately, run

    python test/runtests.py

The required docker image will be built and container started before the tests
are run.

If you are using OS X with `docker-machine`, don't forget to set the
environment variables before running the tests via

    eval "$(docker-machine env <machine>)"

where `<machine>` is your docker-machine name, quite possibly `default`.

The docker container forwards ports 5673 and 15673. Please be sure that
they are available.

Since PulseGuardian is configured via environment variables, you must ensure
that you have a clean environment before running the tests, i.e., no
PulseGuardian environment variables set. (FIXME: set up a full test environment
from within runtests.py rather than relying on defaults.)

Some Linux-specific notes:

* The docker daemon must always run as the root user, but you need to be able
  to run docker client commands without `sudo`. To achieve that you can:

 * Add the docker group if it doesn't already exist:  `sudo groupadd docker`

 * Add the connected user "${USER}" to the docker group. Change the user name
to match your preferred user:  `sudo gpasswd -a ${USER} docker`

 * Restart the Docker daemon:  `sudo service docker restart`

 * You need to log out and log back in again if you added the currently
   logged-in user.

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
