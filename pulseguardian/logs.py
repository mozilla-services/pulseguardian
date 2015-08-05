# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from pulseguardian import config


def setup_logging(filename=None):
    if filename:
        handler = logging.handlers.RotatingFileHandler(
            filename,
            mode='a+',
            maxBytes=config.max_log_size,
            backupCount=config.backup_count)
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s',
                                  '%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    if config.debug_logs:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    return handler
