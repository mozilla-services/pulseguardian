#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from setuptools import setup, Command

class TestCommand(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        import subprocess
        errno = subprocess.call(['python', 'test/runtests.py', '--log=INFO'])
        raise SystemExit(errno)

install_requires = [
    'MozillaPulse',
    'SQLAlchemy',
    'requests',
    'Flask-SSLify',
    'alembic',
    'Flask-pyoidc',
    'Flask',
]

setup(name='PulseGuardian',
      version='0.1',
      description='Monitoring tool and web app for the Pulse ' +
                  'message system: pulse.mozilla.org',
      url='https://wiki.mozilla.org/Auto-tools/Projects/Pulse/PulseGuardian',
      author='Mozilla A-Team',
      author_email='auto-tools@mozilla.com',
      license='MPL 2.0',
      packages=['pulseguardian', 'pulseguardian.model', 'flask_secure_headers'],
      install_requires=install_requires,
      cmdclass={'test': TestCommand}
)
