from functools import partial

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from django.core.signals import request_finished, request_started
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from trac.test import EnvironmentStub, MockRequest
from trac.web.api import RequestDone
from trac.web.main import RequestDispatcher

from tracdjangoplugin.middlewares import DjangoDBManagementMiddleware
from tracdjangoplugin.plugins import PlainLoginComponent


class PlainLoginComponentTestCase(TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.component = PlainLoginComponent(self.env)
        self.request_factory = partial(MockRequest, self.env)

    def test_component_matches_correct_url(self):
        request = self.request_factory(path_info="/login")
        self.assertTrue(self.component.match_request(request))

    def test_component_doesnt_match_another_url(self):
        request = self.request_factory(path_info="/github/login")
        self.assertFalse(self.component.match_request(request))

    def test_component(self):
        request = self.request_factory(path_info="/login")
        template, context = self.component.process_request(request)
        self.assertEqual(template, "plainlogin.html")
        self.assertFalse(context["form"].is_bound)

    def assertLoginSucceeds(
        self, username, password, check_redirect=None, extra_data=None
    ):
        data = {"username": username, "password": password}
        if extra_data is not None:
            data.update(extra_data)
        request = self.request_factory(method="POST", path_info="/login", args=data)
        with self.assertRaises(RequestDone):
            self.component.process_request(request)

        self.assertEqual(request.authname, "test")
        self.assertEqual(request.status_sent, ["303 See Other"])
        if check_redirect is not None:
            redirect_url = request.headers_sent["Location"]
            self.assertEqual(redirect_url, check_redirect)

    def test_login_valid_user(self):
        User.objects.create_user(username="test", password="test")
        self.assertLoginSucceeds(username="test", password="test")

    def test_login_valid_default_redirect(self):
        self.env.config.set("trac", "base_url", "")
        User.objects.create_user(username="test", password="test")
        with self.settings(LOGIN_REDIRECT_URL="/test"):
            self.assertLoginSucceeds(
                username="test", password="test", check_redirect="/test"
            )

    def test_login_valid_with_custom_redirection(self):
        self.env.config.set("trac", "base_url", "")
        User.objects.create_user(username="test", password="test")
        self.assertLoginSucceeds(
            username="test",
            password="test",
            check_redirect="/test",
            extra_data={"next": "/test"},
        )

    def test_login_valid_with_custom_redirection_with_hostname(self):
        self.env.config.set("trac", "base_url", "http://localhost")
        User.objects.create_user(username="test", password="test")
        self.assertLoginSucceeds(
            username="test",
            password="test",
            check_redirect="http://localhost/test",
            extra_data={"next": "http://localhost/test"},
        )

    def test_login_valid_with_malicious_redirection(self):
        self.env.config.set("trac", "base_url", "http://localhost")
        User.objects.create_user(username="test", password="test")
        with self.settings(LOGIN_REDIRECT_URL="/test"):
            self.assertLoginSucceeds(
                username="test",
                password="test",
                check_redirect="http://localhost/test",
                extra_data={"next": "http://example.com/evil"},
            )

    def assertLoginFails(self, username, password, error_message=None):
        if error_message is None:
            error_message = AuthenticationForm.error_messages["invalid_login"] % {
                "username": "username"
            }

        request = self.request_factory(
            method="POST",
            path_info="/login",
            args={"username": username, "password": password},
        )
        template, context = self.component.process_request(request)
        self.assertEqual(template, "plainlogin.html")
        self.assertEqual(context["form"].errors, {"__all__": [error_message]})

    def test_login_invalid_no_users(self):
        self.assertLoginFails(username="test", password="test")

    def test_login_invalid_incorrect_username(self):
        User.objects.create_user(username="test", password="test")
        self.assertLoginFails(username="test123", password="test")

    def test_login_invalid_incorrect_password(self):
        User.objects.create_user(username="test", password="test")
        self.assertLoginFails(username="test", password="test123")

    def test_login_invalid_incorrect_username_and_password(self):
        User.objects.create_user(username="test", password="test")
        self.assertLoginFails(username="test123", password="test123")

    def test_login_invalid_username_uppercased(self):
        User.objects.create_user(username="test", password="test")
        self.assertLoginFails(username="TEST", password="test")

    def test_login_invalid_inactive_user(self):
        User.objects.create_user(username="test", password="test", is_active=False)
        self.assertLoginFails(username="test", password="test")


class DjangoDBManagementMiddlewareTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        # Remove receivers from the request_started and request_finished signals,
        # replacing them with a mock object so we can still check if they were called.
        super(DjangoDBManagementMiddlewareTestCase, cls).setUpClass()
        cls._original_signal_receivers = {}
        cls.signals = {}
        for signal in [request_started, request_finished]:
            cls.signals[signal] = Mock()
            cls._original_signal_receivers[signal] = signal.receivers
            signal.receivers = []
            signal.connect(cls.signals[signal])

    @classmethod
    def tearDownClass(cls):
        # Restore the signals we modified in setUpClass() to what they were before
        super(DjangoDBManagementMiddlewareTestCase, cls).tearDownClass()
        for signal, original_receivers in cls._original_signal_receivers.items():
            # messing about with receivers directly is not an official API, so we need to
            # call some undocumented methods to make sure caches and such are taken care of.
            with signal.lock:
                signal.receivers = original_receivers
                signal._clear_dead_receivers()
                signal.sender_receivers_cache.clear()

    def setUp(self):
        super(DjangoDBManagementMiddlewareTestCase, self).setUp()
        for mockobj in self.signals.values():
            mockobj.reset_mock()

    def test_request_start_fired(self):
        app = DjangoDBManagementMiddleware(lambda environ, start_response: [b"test"])
        output = b"".join(app(None, None))
        self.assertEqual(output, b"test")
        self.signals[request_started].assert_called_once()

    def test_request_finished_fired(self):
        app = DjangoDBManagementMiddleware(lambda environ, start_response: [b"test"])
        output = b"".join(app(None, None))
        self.assertEqual(output, b"test")
        self.signals[request_finished].assert_called_once()

    def test_request_finished_fired_even_with_error(self):
        app = DjangoDBManagementMiddleware(lambda environ, start_response: [1 / 0])
        with self.assertRaises(ZeroDivisionError):
            list(app(None, None))
        self.signals[request_finished].assert_called_once()
