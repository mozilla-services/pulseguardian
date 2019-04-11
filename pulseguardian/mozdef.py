# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import json
import os
import sys

import pulseguardian.config

# Severities
DEBUG = 'DEBUG'
INFO = 'INFO'
NOTICE = 'NOTICE'
WARNING = 'WARNING'
ERROR = 'ERROR'
CRITICAL = 'CRITICAL'
ALERT = 'ALERT'
EMERGENCY = 'EMERGENCY'

# Categories
ACCOUNT_CREATION = 'Account Creation'
ACCOUNT_DELETION = 'Account Deletion'
ACCOUNT_UNLOCK = 'Account Unlock'
ACCOUNT_UPDATE = 'Account Update'
AUTHENTICATION = 'Authentication'
AUTHORIZATION = 'Authorization'
OTHER = 'Other'
SHUTDOWN = 'Shutdown'
STARTUP = 'Startup'


def log(sev, cat, summary, details=None, tags=None):
    print '[{}] {} {} {}'.format(cat, summary, json.dumps(details), json.dumps(tags))

