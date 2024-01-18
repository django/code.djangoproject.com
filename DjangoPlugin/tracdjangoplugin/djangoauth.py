"""
WSGI middleware that authenticates against a Django user database.

DJANGO_SETTINGS_MODULE should point to a valid Django settings module.

In addition, the following settings are available:

- BASIC_AUTH_LOGIN_URL: DjangoAuth will trigger basic authentication on this
  URL. Since browsers only propagate auth to resources on the same level or
  below, this URL will usually be '/<something>' without a trailing slash.
  Defaults to '/login'.
- BASIC_AUTH_MESSAGE: Content of the 401 error page. Defaults to
  "Authorization required.".
- BASIC_AUTH_MESSAGE_TYPE: Content type of the message. Defaults to
  'text/plain'.
- BASIC_AUTH_REALM: Authentication realm. Defaults to "Authenticate".
- BASIC_AUTH_REDIRECT_URL: DjangoAuth will redirect to this URL after login if
  it isn't empty and to the HTTP Referer otherwise. If provided, it should be
  an absolute URL including the domain name. Defaults to ''.

If the user authenticates successfully, the REMOTE_USER variable is set in the
WSGI environment.

See http://tools.ietf.org/html/rfc2617#section-2 for details on basic auth.
"""

from base64 import b64decode

import django
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.handlers.wsgi import get_path_info
from django.db import close_old_connections
from django.utils import six


django.setup()


class DjangoAuth:
    login_url = getattr(settings, "BASIC_AUTH_LOGIN_URL", "/login")
    message = getattr(settings, "BASIC_AUTH_MESSAGE", "Authorization required.")
    message_type = getattr(settings, "BASIC_AUTH_MESSAGE_TYPE", "text/plain")
    realm = getattr(settings, "BASIC_AUTH_REALM", "Authenticate")

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        try:
            if get_path_info(environ) == self.login_url:
                username = self.process_authorization(environ)
                if username is None:
                    start_response(
                        "401 Unauthorized",
                        [
                            ("Content-Type", self.message_type),
                            ("WWW-Authenticate", 'Basic realm="%s"' % self.realm),
                        ],
                    )
                    return [self.message]
        finally:
            close_old_connections()

        return self.application(environ, start_response)

    @staticmethod
    def process_authorization(environ):
        # Don't override authentication information set by another component.
        remote_user = environ.get("REMOTE_USER")
        if remote_user is not None:
            return

        authorization = environ.get("HTTP_AUTHORIZATION")
        if authorization is None:
            return

        if six.PY3:  # because fuck you PEP 3333.
            authorization = authorization.encode("iso-8859-1").decode("utf-8")

        method, _, credentials = authorization.partition(" ")
        if not method.lower() == "basic":
            return

        try:
            credentials = b64decode(credentials.strip())
            username, _, password = credentials.partition(":")
        except Exception:
            return

        if authenticate(username=username, password=password) is None:
            return

        remote_user = username

        if six.PY3:  # because fuck you PEP 3333.
            remote_user = remote_user.encode("utf-8").decode("iso-8859-1")

        environ["REMOTE_USER"] = remote_user

        return username
