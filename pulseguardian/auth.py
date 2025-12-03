# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import functools

from authlib.integrations.flask_client import OAuth
from authlib.jose import JsonWebKey
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

        # Initialize OAuth without cache - use Flask's session cookies instead
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

        # Allow HS* tokens by falling back to client_secret when no JWKS key matches.
        auth0_app = self.oauth.auth0

        def create_load_key_with_hs_fallback():
            def load_key(header, _):
                jwk_set = JsonWebKey.import_key_set(auth0_app.fetch_jwk_set())
                try:
                    return jwk_set.find_by_kid(
                        header.get("kid"), use="sig", alg=header.get("alg")
                    )
                except ValueError:
                    alg = header.get("alg", "")
                    if alg.startswith("HS"):
                        # TODO: Reconfigure Auth0 to use RS256 instead of HS256
                        return JsonWebKey.import_key(
                            config.oidc_client_secret,
                            {"kty": "oct", "use": "sig", "alg": alg},
                        )
                    raise

            return load_key

        auth0_app.create_load_key = create_load_key_with_hs_fallback

        return self

    def oidc_auth(self, view_func):
        """Decorator requiring authentication."""

        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if "userinfo" not in session:
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)

        return wrapper

    def oidc_logout(self, view_func):
        """Decorator for logout endpoint"""

        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            session.clear()
            return view_func(*args, **kwargs)

        return wrapper
