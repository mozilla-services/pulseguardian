# PulseGuardian

A system to manage Pulse: administers RabbitMQ users and handles overgrowing
queues. More information on [the wiki][].

[![Build Status](https://travis-ci.org/mozilla-services/pulseguardian.svg?branch=master)](https://travis-ci.org/mozilla-services/pulseguardian)

## Pre-requisites

* RabbitMQ (tested on 3.5.7)
* Python 3.6
* pip (to install external dependencies)
* PostgreSQL (for production; testing environments can use sqlite)
* docker-compose (to stand up a local Docker-based environment)

## Setup

### Docker Compose

The easiest way to start a local instance of PulseGuardian is via
[docker-compose][]:

    $ docker-compose up --build

This will launch four containers: a RabbitMQ instance, a PostGreSQL database,
the PulseGuardian web process, and the PulseGuardian daemon
(`guardian.py`).  Pressing control-C will stop all the containers.
You can also add `-d` to run docker-compose in the background, in
which case you will need to run `docker-compose down` to stop the containers.

Known issue: a local install of PostGreSQL will likely result in a port
conflict.

The PulseGuardian code is mounted as `/code` in the web and daemon
containers.  You can edit the code locally and restart the container(s) to
pick up changes: `docker-compose restart web` and/or `docker-compose
restart guardian`.  The RabbitMQ cluster and PulseGuardian database data are
preserved across restarts as via Docker volumes.

Because PulseGuardian uses cookies, it is necessary to add an entry to
your local hosts file for `pulseguardian-web`, mapping to 127.0.0.1.
After adding this, you can access the web server via
http://pulseguardian-web:5000/.

RabbitMQ is available via localhost:5672 (AMQP) and
http://localhost:15672/ (management interface).  The PostGreSQL
database is available at localhost:5432.  If you have `psql` installed
locally, you can connect to the database via the following:

    psql -h localhost -p 5432 -d postgres -U postgres

You can change the logged-in user by overriding the `FAKE_ACCOUNT`
environment variable.  One way to do this is by creating a file named
`docker-compose.override.yml` that contains something like this:

```yml
version: "2"
services:
  pulseguardian-web:
    environment:
      - FAKE_ACCOUNT=fake-override@example.com
```

### Local

You can also run the web and/or daemon processes locally.

On Linux (or the Linux subsystem on Windows 10), you will need some
system packages installed before you can install the prerequisite Python
packages.  On Ubuntu, these are

* python
* python-dev
* libssl-dev
* libffi-dev 

You will also need PostgreSQL installed in order to install the psycopg2
Python package.

Using a virtualenv is highly recommended. One possible installation would be

* Clone the repository and cd into it.
* Create and activate a virtualenv:

        virtualenv venv
        source venv/bin/activate

Within the chosen environment, install and configure PulseGuardian:

* Install the requirements:

        pip install -r requirements.txt

* Install the package.  This will ensure you have access to the `pulseguardian`
  package from anywhere in your virtualenv.

        python setup.py develop

If you will be running PulseGuardian with SSL enabled (i.e. over https),
you will also need the pyOpenSSL package:

    pip install pyOpenSSL

You will also need a RabbitMQ instance running somewhere.  Docker provides a
lightweight and isolated solution.  See the [docker installation docs][] for
your system.

To create a Pulse Docker image, run this from within the root PulseGuardian
source directory:

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

```bash
export FLASK_SECRET_KEY=`python gen_secret_key.py`
export DATABASE_URL=sqlite:///`pwd`/db
```

See the complete listing of options in `pulseguardian/config.py`.

TODO: Each of these options should be documented in the source.

Initialize the db with `python pulseguardian/dbinit.py`. *WARNING*:
This removes any existing data the app might have previously stored in
the database.

Set the environment variable `FAKE_ACCOUNT` to a valid email address.
This setting makes development easier by bypassing OIDC
authentication, logging the user in automatically with the provided
address.  It will also create the given user, if necessary.

You can also test with a real Auth0 account.  You can create an account at
https://auth0.com and use the provided credentials in the `OIDC_*` config
variables.

Run the Pulse Guardian daemon with: `python pulseguardian/guardian.py`

Run the web app (for development) with: `python pulseguardian/web.py`

For production, the web app can be run with [gunicorn][] and such.

## Testing

TODO: This process should be updated to run the tests with a
docker-compose environment.

Tests are automatically run against the GitHub repository via [Travis
CI][]. Before submitting a patch, it is highly recommended that you
get a Travis CI account and activate it on a GitHub fork of the
pulseguardian repo.

For local testing, PulseGuardian uses docker to run its test
suite. Please follow the [docker installation docs][] on how to
install it in your system.  Note that these tests are not yet hooked
up to the environment created with `docker-compose` above.

With docker installed and configured appropriately, run

    python test/runtests.py

The required docker image will be built and container started before the tests
are run.

The docker container forwards ports 5672 and 15672. Please be sure that
they are available.

Since PulseGuardian is configured via environment variables, you must ensure
that you have a clean environment before running the tests, i.e., no
PulseGuardian environment variables set. (FIXME: set up a full test environment
from within runtests.py rather than relying on defaults.)

Some Linux-specific notes (TODO: are these still valid/necessary?):

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

## Database migration

PulseGuardian uses [Alembic][] for database migrations.  SQLite doesn't support
all the SQL commands required for migrations, so you may want to use PostgreSQL
even in your development environment, at least if you are testing migrations.

Because PulseGuardian is designed to run on Heroku, which doesn't support
locally modified files, the Alembic configuration file, `alembic.ini`, must be
used for all installations, including for local development.  The database URL,
`sqlalchemy.url`, is not used; instead, `migration/env.py` is set to use the
`DATABASE_URL` environment variable, as the rest of PulseGuardian does.

To migrate the database,

* Install the alembic package (if you haven't yet): `pip install -r
  requirements.txt`
* Run `alembic upgrade head`

## Deployment

This project is deployed to the Heroku app `pulseguardian`.
This is via Git pushes to Heroku, rather than the more common pull-from-GitHub approach.
To set this up, run `heroku git:remote -a pulseguardian`.
Then just push the latest `master` branch to the `heroku` remote.

[the wiki]: https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian
[docker-compose]: https://docs.docker.com/compose/
[HACKING.md]: https://hg.mozilla.org/automation/mozillapulse/file/tip/HACKING.md
[Travis CI]: https://travis-ci.org/mozilla/pulseguardian
[gunicorn]: https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx
[docker installation docs]: https://docs.docker.com/installation/#installation
[Alembic]: https://alembic.readthedocs.org
