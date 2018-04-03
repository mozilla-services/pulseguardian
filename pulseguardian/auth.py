# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import functools

from flask_pyoidc.flask_pyoidc import OIDCAuthentication

from pulseguardian import config


class FakeOIDCAuthentication(object):
    """Fake auth provider, for use with the FAKE_ACCOUNT setting."""

    def oidc_auth(self, view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapper

    def oidc_logout(self, view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapper


class OpenIDConnect(object):
    """Auth object for login, logout, and response validation."""

    def client_info(self):
        return dict(
            client_id=config.oidc_client_id,
            client_secret=config.oidc_client_secret,
        )

    def auth(self, app):
        if config.fake_account:
            return FakeOIDCAuthentication()

        oidc = OIDCAuthentication(
            app,
            issuer='https://{DOMAIN}/'.format(DOMAIN=config.oidc_domain),
            client_registration_info=self.client_info(),
            extra_request_args={
                'scope': ['openid', 'profile', 'email'],
            },
        )
        return oidc
