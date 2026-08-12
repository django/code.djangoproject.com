"""External authentication bridge for code.djangoproject.com.

The companion djangoproject.com endpoint authenticates the user and returns a
short-lived JWT assertion to ``/django-auth/callback``.
"""

import os
import secrets
from urllib.parse import urlencode, urlsplit

import jwt
from trac.core import implements
from trac.util.html import html as tag
from trac.web.api import IRequestHandler, HTTPMethodNotAllowed
from trac.web.auth import LoginModule
from trac.web.chrome import INavigationContributor, add_warning


ASSERTION_ISSUER = "https://www.djangoproject.com/"
ASSERTION_AUDIENCE = "code.djangoproject.com"
SHARED_SECRET_ENV = "DJANGO_TRAC_AUTH_SECRET"
CLOCK_SKEW = 10


class InvalidAssertion(ValueError):
    """Raised when an external authentication assertion is invalid."""


def verify_assertion(
    token: str,
    *,
    secret: str,
    expected_state: str,
) -> dict:
    """Verify an authentication assertion issued by djangoproject.com."""

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=ASSERTION_AUDIENCE,
            issuer=ASSERTION_ISSUER,
            leeway=CLOCK_SKEW,
            options={
                "require": [
                    "sub",
                    "aud",
                    "iss",
                    "iat",
                    "exp",
                    "state",
                ],
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidAssertion("Invalid authentication assertion") from exc

    subject = claims["sub"]
    if (
        not isinstance(subject, str)
        or not subject
        or subject == "anonymous"
        or any(character.isspace() for character in subject)
    ):
        raise InvalidAssertion("Invalid subject")

    state = claims["state"]
    if not isinstance(state, str) or state != expected_state:
        raise InvalidAssertion("Invalid state")

    return claims


class DjangoExternalLoginModule(LoginModule):
    """Delegate authentication to djangoproject.com and create a Trac session."""

    implements(IRequestHandler, INavigationContributor)

    auth_url = "https://www.djangoproject.com/accounts/trac/login/"

    login_path = "/django-auth/login"
    callback_path = "/django-auth/callback"
    logout_path = "/django-auth/logout"

    state_session_key = "django_auth_state"
    next_session_key = "django_auth_next"

    # INavigationContributor

    def get_active_navigation_item(self, req):
        return "django_login"

    def get_navigation_items(self, req):
        if req.authname and req.authname != "anonymous":
            yield (
                "metanav",
                "login",
                f"logged in as {req.authname}",
            )
            yield (
                "metanav",
                "logout",
                tag.form(
                    tag.div(
                        tag.input(
                            type="hidden",
                            name="__FORM_TOKEN",
                            value=req.form_token,
                        ),
                        tag.button(
                            "Logout",
                            name="logout",
                            type="submit",
                        ),
                    ),
                    action=req.href(self.logout_path),
                    method="post",
                    id="logout",
                    class_="trac-logout",
                ),
            )
        else:
            yield (
                "metanav",
                "django_login",
                tag.a(
                    "Django account login",
                    href=req.href(self.login_path),
                ),
            )

    # IRequestHandler

    def match_request(self, req):
        return req.path_info in {
            self.login_path,
            self.callback_path,
            self.logout_path,
        }

    def process_request(self, req):
        if req.path_info == self.login_path:
            return self._start_external_login(req)

        if req.path_info == self.callback_path:
            return self._finish_external_login(req)

        if req.path_info == self.logout_path:
            return self._logout(req)

        raise AssertionError(f"Unexpected authentication path: {req.path_info}")

    def _start_external_login(self, req):
        state = secrets.token_urlsafe(32)

        req.session[self.state_session_key] = state
        req.session[self.next_session_key] = self._safe_local_path(
            req.args.get("referer") or req.get_header("Referer")
        )

        callback_url = req.abs_href(self.callback_path.lstrip("/"))
        query = urlencode(
            {
                "state": state,
                "callback": callback_url,
            }
        )

        req.redirect(f"{self.auth_url}?{query}")

    def _finish_external_login(self, req):
        state = req.session.pop(self.state_session_key, None)
        if not state:
            self._reject(
                req,
                "Login session expired. Please try again.",
            )

        token = req.args.get("assertion")
        if not token:
            self._reject(
                req,
                "The login response did not include an assertion.",
            )

        secret = os.environ.get(SHARED_SECRET_ENV)
        if not secret:
            self.log.error(
                "Django authentication environment variable %s is not set",
                SHARED_SECRET_ENV,
            )
            self._reject(
                req,
                "Django account login is not configured.",
            )

        try:
            claims = verify_assertion(
                token,
                secret=secret,
                expected_state=state,
            )
        except InvalidAssertion as exc:
            self.log.warning(
                "Rejected Django authentication assertion: %s",
                exc,
            )
            self._reject(
                req,
                "Invalid or expired login response. Please try again.",
            )

        req.environ["REMOTE_USER"] = claims["sub"]

        name = claims.get("name")
        if isinstance(name, str):
            req.session["name"] = name

        email = claims.get("email")
        if isinstance(email, str):
            req.session["email"] = email

        super()._do_login(req)

        self._redirect_to_local_path(
            req,
            req.session.pop(self.next_session_key, None),
        )

    def _logout(self, req):
        if req.method != "POST":
            raise HTTPMethodNotAllowed("Logout requires a POST request.")

        self._do_logout(req)
        self._redirect_to_local_path(req, req.args.get("referer"))

    def _reject(self, req, message):
        req.session.pop(self.next_session_key, None)
        add_warning(req, message)
        self._redirect_to_local_path(req, None)

    def _redirect_to_local_path(self, req, candidate):
        req.redirect(req.abs_href(self._safe_local_path(candidate)))

    @staticmethod
    def _safe_local_path(candidate):
        """Return a local path, rejecting external redirect targets."""

        if not candidate:
            return "/"

        parsed = urlsplit(candidate)

        if parsed.scheme or parsed.netloc:
            return "/"

        if not parsed.path.startswith("/") or parsed.path.startswith("//"):
            return "/"

        result = parsed.path
        if parsed.query:
            result += f"?{parsed.query}"

        return result
