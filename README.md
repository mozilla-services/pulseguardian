# PulseGuardian

A system to manage Pulse: creates users and handle overgrowing queues. More information on [the wiki](https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian).

## Pre-requisites

* RabbitMQ (tested on 3.3.0)
* Python (2.7.x)
* pip (to install external dependencies)
* MySQL (if you're using the sqlalchemy MySQL engine, see below)

## Setup

* Clone the repository and cd into it
* Create and activatea virtualenv:
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

Make sure rabbitmq-server is running before you run.

* Initialize the db and create some dummy data with: `python src/dbinit.py`
* Run the Pulse Guardian daemon with: `python src/guardian.py`
* Run the web app (for development) with: `python src/web.py`
* For production, the web app can be run with [gunicorn](https://www.digitalocean.com/community/articles/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx) and such.
* Run tests with: `python src/runtest.py`
