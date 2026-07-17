"""Tests for the external Django authentication bridge."""

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch
from urllib.parse import parse_qs, urlsplit

import jwt
from trac.test import EnvironmentStub
from trac.web.api import HTTPMethodNotAllowed
from trac.web.auth import LoginModule

from .plugins import (
    ASSERTION_AUDIENCE,
    ASSERTION_ISSUER,
    SHARED_SECRET_ENV,
    DjangoExternalLoginModule,
    InvalidAssertion,
    verify_assertion,
)


SECRET = "test-secret-that-is-long-enough-for-tests"
STATE = "test-login-state"
USERNAME = "alice"


class Redirected(Exception):
    """Raised by test doubles when code attempts to redirect."""


def make_assertion(
    *,
    secret=SECRET,
    state=STATE,
    subject=USERNAME,
    issuer=ASSERTION_ISSUER,
    audience=ASSERTION_AUDIENCE,
    issued_at=None,
    expires_at=None,
    algorithm="HS256",
    **extra_claims,
):
    """Create a JWT assertion for tests."""

    now = int(time.time())
    issued_at = now if issued_at is None else issued_at
    expires_at = now + 60 if expires_at is None else expires_at

    claims = {
        "sub": subject,
        "aud": audience,
        "iss": issuer,
        "iat": issued_at,
        "exp": expires_at,
        "state": state,
        **extra_claims,
    }

    return jwt.encode(
        claims,
        secret,
        algorithm=algorithm,
    )


def make_request(
    *,
    path_info="/",
    method="GET",
    args=None,
    session=None,
    authname="anonymous",
    referer=None,
):
    """Create the minimal request object required by the component."""

    headers = {}
    if referer is not None:
        headers["Referer"] = referer

    request = SimpleNamespace(
        path_info=path_info,
        method=method,
        args={} if args is None else args,
        session={} if session is None else session,
        environ={},
        authname=authname,
        form_token="test-form-token",
        href=lambda path: path,
        abs_href=lambda path="": f"https://code.djangoproject.com/{path}",
        get_header=lambda name: headers.get(name),
    )

    return request


class VerifyAssertionTestCase(unittest.TestCase):
    def test_valid_assertion(self):
        token = make_assertion(
            name="Alice Example",
            email="alice@example.com",
        )

        claims = verify_assertion(
            token,
            secret=SECRET,
            expected_state=STATE,
        )

        self.assertEqual(USERNAME, claims["sub"])
        self.assertEqual("Alice Example", claims["name"])
        self.assertEqual("alice@example.com", claims["email"])

    def test_rejects_wrong_secret(self):
        token = make_assertion()

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret="wrong-secret",
                expected_state=STATE,
            )

    def test_rejects_wrong_state(self):
        token = make_assertion()

        with self.assertRaisesRegex(InvalidAssertion, "Invalid state"):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state="different-state",
            )

    def test_rejects_non_string_state(self):
        token = make_assertion(state=123)

        with self.assertRaisesRegex(InvalidAssertion, "Invalid state"):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_wrong_audience(self):
        token = make_assertion(audience="another-service")

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_wrong_issuer(self):
        token = make_assertion(issuer="https://example.com/")

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_expired_assertion(self):
        now = int(time.time())
        token = make_assertion(
            issued_at=now - 120,
            expires_at=now - 60,
        )

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_allows_expiration_within_clock_skew(self):
        now = int(time.time())
        token = make_assertion(
            issued_at=now - 60,
            expires_at=now - 5,
        )

        claims = verify_assertion(
            token,
            secret=SECRET,
            expected_state=STATE,
        )

        self.assertEqual(USERNAME, claims["sub"])

    def test_rejects_missing_required_claim(self):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": USERNAME,
                "aud": ASSERTION_AUDIENCE,
                "iss": ASSERTION_ISSUER,
                "iat": now,
                "exp": now + 60,
                # state deliberately omitted
            },
            SECRET,
            algorithm="HS256",
        )

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_empty_subject(self):
        token = make_assertion(subject="")

        with self.assertRaisesRegex(InvalidAssertion, "Invalid subject"):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_anonymous_subject(self):
        token = make_assertion(subject="anonymous")

        with self.assertRaisesRegex(InvalidAssertion, "Invalid subject"):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )

    def test_rejects_subject_containing_whitespace(self):
        for subject in ("alice smith", "alice\nsmith", " alice"):
            with self.subTest(subject=subject):
                token = make_assertion(subject=subject)

                with self.assertRaisesRegex(
                    InvalidAssertion,
                    "Invalid subject",
                ):
                    verify_assertion(
                        token,
                        secret=SECRET,
                        expected_state=STATE,
                    )

    def test_rejects_non_string_subject(self):
        token = make_assertion(subject=123)

        with self.assertRaisesRegex(
            InvalidAssertion,
            "Invalid authentication assertion",
        ):
            verify_assertion(
                token,
                secret=SECRET,
                expected_state=STATE,
            )


class DjangoExternalLoginModuleTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.module = DjangoExternalLoginModule(self.env)

    def tearDown(self):
        self.env.shutdown()

    def test_matches_authentication_paths(self):
        matching_paths = (
            "/django-auth/login",
            "/django-auth/callback",
            "/django-auth/logout",
        )

        for path in matching_paths:
            with self.subTest(path=path):
                req = make_request(path_info=path)
                self.assertTrue(self.module.match_request(req))

    def test_does_not_match_other_or_trailing_slash_paths(self):
        nonmatching_paths = (
            "/",
            "/login",
            "/django-auth/login/",
            "/django-auth/callback/",
            "/django-auth/logout/",
        )

        for path in nonmatching_paths:
            with self.subTest(path=path):
                req = make_request(path_info=path)
                self.assertFalse(self.module.match_request(req))

    def test_safe_local_path_accepts_local_path(self):
        self.assertEqual(
            "/ticket/123?format=rss",
            self.module._safe_local_path("/ticket/123?format=rss"),
        )

    def test_safe_local_path_ignores_fragment(self):
        self.assertEqual(
            "/ticket/123",
            self.module._safe_local_path("/ticket/123#comment:1"),
        )

    def test_safe_local_path_rejects_external_urls(self):
        unsafe_values = (
            None,
            "",
            "ticket/123",
            "https://example.com/",
            "//example.com/path",
            "javascript:alert(1)",
        )

        for value in unsafe_values:
            with self.subTest(value=value):
                self.assertEqual(
                    "/",
                    self.module._safe_local_path(value),
                )

    def test_start_login_saves_state_and_safe_destination(self):
        session = {}
        req = make_request(
            path_info=self.module.login_path,
            args={"referer": "/ticket/123?format=rss"},
            session=session,
        )
        req.redirect = Mock(side_effect=Redirected)

        with self.assertRaises(Redirected):
            self.module._start_external_login(req)

        self.assertIn(self.module.state_session_key, session)
        self.assertTrue(session[self.module.state_session_key])
        self.assertEqual(
            "/ticket/123?format=rss",
            session[self.module.next_session_key],
        )

        redirect_url = req.redirect.call_args.args[0]
        parsed = urlsplit(redirect_url)
        query = parse_qs(parsed.query)

        self.assertEqual(
            "https://www.djangoproject.com/accounts/trac/login/",
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        )
        self.assertEqual(
            [session[self.module.state_session_key]],
            query["state"],
        )
        self.assertEqual(
            ["https://code.djangoproject.com/django-auth/callback"],
            query["callback"],
        )

    def test_start_login_rejects_external_referer(self):
        session = {}
        req = make_request(
            path_info=self.module.login_path,
            args={"referer": "https://attacker.example/path"},
            session=session,
        )
        req.redirect = Mock(side_effect=Redirected)

        with self.assertRaises(Redirected):
            self.module._start_external_login(req)

        self.assertEqual("/", session[self.module.next_session_key])

    def test_start_login_uses_referer_header(self):
        session = {}
        req = make_request(
            path_info=self.module.login_path,
            session=session,
            referer="/wiki/Django",
        )
        req.redirect = Mock(side_effect=Redirected)

        with self.assertRaises(Redirected):
            self.module._start_external_login(req)

        self.assertEqual(
            "/wiki/Django",
            session[self.module.next_session_key],
        )

    @patch.dict(os.environ, {SHARED_SECRET_ENV: SECRET}, clear=False)
    def test_finish_login_authenticates_and_redirects(self):
        token = make_assertion(
            name="Alice Example",
            email="alice@example.com",
        )
        session = {
            self.module.state_session_key: STATE,
            self.module.next_session_key: "/ticket/123",
        }
        req = make_request(
            path_info=self.module.callback_path,
            args={"assertion": token},
            session=session,
        )

        with (
            patch.object(LoginModule, "_do_login") as do_login,
            patch.object(
                self.module,
                "_redirect_to_local_path",
                side_effect=Redirected,
            ) as redirect,
        ):
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        self.assertEqual(USERNAME, req.environ["REMOTE_USER"])
        self.assertEqual("Alice Example", session["name"])
        self.assertEqual("alice@example.com", session["email"])
        self.assertNotIn(self.module.state_session_key, session)
        self.assertNotIn(self.module.next_session_key, session)

        do_login.assert_called_once_with(req)
        redirect.assert_called_once_with(req, "/ticket/123")

    @patch.dict(os.environ, {SHARED_SECRET_ENV: SECRET}, clear=False)
    def test_finish_login_ignores_non_string_optional_claims(self):
        token = make_assertion(
            name=["Alice"],
            email={"address": "alice@example.com"},
        )
        session = {
            self.module.state_session_key: STATE,
            self.module.next_session_key: "/",
        }
        req = make_request(
            path_info=self.module.callback_path,
            args={"assertion": token},
            session=session,
        )

        with (
            patch.object(LoginModule, "_do_login"),
            patch.object(
                self.module,
                "_redirect_to_local_path",
                side_effect=Redirected,
            ),
        ):
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        self.assertNotIn("name", session)
        self.assertNotIn("email", session)

    def test_finish_login_rejects_missing_session_state(self):
        req = make_request(
            path_info=self.module.callback_path,
            args={"assertion": make_assertion()},
        )

        with patch.object(
            self.module,
            "_reject",
            side_effect=Redirected,
        ) as reject:
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        reject.assert_called_once_with(req, ANY)

    @patch.dict(os.environ, {SHARED_SECRET_ENV: SECRET}, clear=False)
    def test_finish_login_rejects_missing_assertion(self):
        req = make_request(
            path_info=self.module.callback_path,
            session={self.module.state_session_key: STATE},
        )

        with patch.object(
            self.module,
            "_reject",
            side_effect=Redirected,
        ) as reject:
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        reject.assert_called_once_with(req, ANY)
        self.assertNotIn(self.module.state_session_key, req.session)

    @patch.dict(os.environ, {}, clear=True)
    def test_finish_login_rejects_missing_secret(self):
        req = make_request(
            path_info=self.module.callback_path,
            args={"assertion": make_assertion()},
            session={self.module.state_session_key: STATE},
        )

        with patch.object(
            self.module,
            "_reject",
            side_effect=Redirected,
        ) as reject:
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        reject.assert_called_once_with(req, ANY)

    @patch.dict(os.environ, {SHARED_SECRET_ENV: SECRET}, clear=False)
    def test_finish_login_rejects_invalid_assertion(self):
        req = make_request(
            path_info=self.module.callback_path,
            args={"assertion": make_assertion(state="wrong-state")},
            session={
                self.module.state_session_key: STATE,
                self.module.next_session_key: "/ticket/123",
            },
        )

        with patch.object(
            self.module,
            "_reject",
            side_effect=Redirected,
        ) as reject:
            with self.assertRaises(Redirected):
                self.module._finish_external_login(req)

        reject.assert_called_once_with(req, ANY)

    def test_logout_requires_post(self):
        req = make_request(
            path_info=self.module.logout_path,
            method="GET",
        )

        with self.assertRaises(HTTPMethodNotAllowed):
            self.module._logout(req)

    def test_logout_posts_and_redirects(self):
        req = make_request(
            path_info=self.module.logout_path,
            method="POST",
            args={"referer": "/ticket/123"},
        )

        with (
            patch.object(self.module, "_do_logout") as do_logout,
            patch.object(
                self.module,
                "_redirect_to_local_path",
                side_effect=Redirected,
            ) as redirect,
        ):
            with self.assertRaises(Redirected):
                self.module._logout(req)

        do_logout.assert_called_once_with(req)
        redirect.assert_called_once_with(req, "/ticket/123")

    def test_process_request_routes_login(self):
        req = make_request(path_info=self.module.login_path)

        with patch.object(
            self.module,
            "_start_external_login",
            return_value="login-result",
        ) as handler:
            result = self.module.process_request(req)

        self.assertEqual("login-result", result)
        handler.assert_called_once_with(req)

    def test_process_request_routes_callback(self):
        req = make_request(path_info=self.module.callback_path)

        with patch.object(
            self.module,
            "_finish_external_login",
            return_value="callback-result",
        ) as handler:
            result = self.module.process_request(req)

        self.assertEqual("callback-result", result)
        handler.assert_called_once_with(req)

    def test_process_request_routes_logout(self):
        req = make_request(path_info=self.module.logout_path)

        with patch.object(
            self.module,
            "_logout",
            return_value="logout-result",
        ) as handler:
            result = self.module.process_request(req)

        self.assertEqual("logout-result", result)
        handler.assert_called_once_with(req)

    def test_process_request_rejects_unexpected_path(self):
        req = make_request(path_info="/unexpected")

        with self.assertRaisesRegex(
            AssertionError,
            "Unexpected authentication path",
        ):
            self.module.process_request(req)


if __name__ == "__main__":
    unittest.main()
