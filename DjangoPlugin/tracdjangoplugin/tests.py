from functools import partial

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.test import TestCase

from trac.test import EnvironmentStub, MockRequest
from trac.web.api import RequestDone
from trac.web.main import RequestDispatcher

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
