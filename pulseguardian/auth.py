# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import functools

from authlib.integrations.flask_client import OAuth
from flask import redirect, session, url_for

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
    """Auth object for login, logout, and response validation using authlib."""

    def __init__(self):
        self.oauth = None

    def auth(self, app):
        if config.fake_account:
            return FakeOIDCAuthentication()

        self.oauth = OAuth(app)

        # Register Auth0 as an OAuth provider
        self.oauth.register(
            name="auth0",
            client_id=config.oidc_client_id,
            client_secret=config.oidc_client_secret,
            server_metadata_url=f"https://{config.oidc_domain}/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid profile email",
            },
        )

        return self

    def oidc_auth(self, view_func):
        """Decorator requiring authentication."""

        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if "userinfo" not in session:
                # Redirect to login route if not authenticated
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)

        return wrapper

    def oidc_logout(self, view_func):
        """Decorator for logout endpoint."""

        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            # Execute the view function
            result = view_func(*args, **kwargs)

            # Clear session
            session.clear()

            # Redirect to Auth0 logout endpoint
            return redirect(
                f"https://{config.oidc_domain}/v2/logout?"
                f"client_id={config.oidc_client_id}&"
                f"returnTo={url_for('index', _external=True)}"
            )

        return wrapper
