from functools import partial

from unittest.mock import Mock

from django.core.signals import request_finished, request_started
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from trac.mimeview.api import Mimeview
from trac.mimeview.rst import (
    ReStructuredTextRenderer,  # noqa: needed for RSTWikiTestCase to work
)
from trac.perm import PermissionSystem
from trac.test import EnvironmentStub, MockRequest
from trac.ticket.model import Ticket
from trac.web.api import RequestDone

from tracdjangoplugin.middlewares import DjangoDBManagementMiddleware
from tracdjangoplugin.plugins import (
    PlainLoginComponent,
    ReservedUsernamesComponent,
    TicketAssignmentValidator,
    TimelineTicketComponentFilter,
)


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
            extra_data={"referer": "/test"},
        )

    def test_login_valid_with_custom_redirection_with_hostname(self):
        self.env.config.set("trac", "base_url", "http://localhost")
        User.objects.create_user(username="test", password="test")
        self.assertLoginSucceeds(
            username="test",
            password="test",
            check_redirect="http://localhost/test",
            extra_data={"referer": "http://localhost/test"},
        )

    def test_login_valid_with_malicious_redirection(self):
        self.env.config.set("trac", "base_url", "http://localhost")
        User.objects.create_user(username="test", password="test")

        # adapted from django/tests/auth_tests/test_views.py
        for redirect_url in [
            "http://example.com",
            "http://example.com/evil",
            "http:///example.com",
            "https://example.com",
            "ftp://example.com",
            "///example.com",
            "//example.com",
            'javascript:alert("XSS")',
        ]:
            with self.subTest(url=redirect_url), self.settings(
                LOGIN_REDIRECT_URL="/test"
            ):
                self.assertLoginSucceeds(
                    username="test",
                    password="test",
                    check_redirect="http://localhost/test",
                    extra_data={"referer": redirect_url},
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

    def test_login_page_redirects_if_already_logged_in(self):
        self.env.config.set("trac", "base_url", "")
        request = self.request_factory(
            method="GET",
            path_info="/login",
            args={"referer": "/test"},
            authname="admin",
        )

        with self.assertRaises(RequestDone):
            self.component.process_request(request)

        self.assertEqual(request.headers_sent["Location"], "/test")


class DjangoDBManagementMiddlewareTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        # Remove receivers from the request_started and request_finished signals,
        # replacing them with a mock object so we can still check if they were called.
        super().setUpClass()
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
        super().tearDownClass()
        for signal, original_receivers in cls._original_signal_receivers.items():
            # messing about with receivers directly is not an official API, so we need to
            # call some undocumented methods to make sure caches and such are taken care of.
            with signal.lock:
                signal.receivers = original_receivers
                signal._clear_dead_receivers()
                signal.sender_receivers_cache.clear()

    def setUp(self):
        super().setUp()
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


class ReservedUsernamesComponentTestCase(TestCase):
    def setUp(self):
        self.env = EnvironmentStub(
            config=[("djangoplugin", "reserved_usernames", "invalid")]
        )
        self.component = ReservedUsernamesComponent(self.env)
        self.request_factory = partial(MockRequest, self.env)

    def test_reserved_name_redirect(self):
        request = self.request_factory(
            path_info="/", script_name="", authname="invalid"
        )
        with self.assertRaises(RequestDone):
            self.component.pre_process_request(
                request, handler=None
            )  # handler doesn't matter here

        redirect_url = request.headers_sent["Location"]
        # Trac's EnvironmentStub uses http://example.org by as a base_url
        self.assertEqual(redirect_url, "http://example.org/login?reserved=invalid")

    def test_non_reserved_name_goes_through(self):
        request = self.request_factory(path_info="/", authname="valid")
        handler = object()
        retval = self.component.pre_process_request(request, handler=handler)
        self.assertIs(retval, handler)

    def test_anonymous_goes_through(self):
        request = self.request_factory(path_info="/")
        handler = object()
        retval = self.component.pre_process_request(request, handler=handler)
        self.assertIs(retval, handler)


class TimelineTicketComponentFilterTestCase(SimpleTestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        self.filter = TimelineTicketComponentFilter(self.env)
        self.request_factory = partial(MockRequest, self.env)

    def make_ticket_event(self, kind, component):
        data = [None] * 11
        data[TimelineTicketComponentFilter._TICKET_COMPONENT_INDEX] = component
        return {"kind": kind, "data": tuple(data)}

    def make_non_ticket_event(self, kind="wiki"):
        return {"kind": kind, "data": ()}

    def post_process(self, req, events):
        return self.filter.post_process_request(
            req, "timeline.rss", {"events": events}, {}
        )

    def test_keeps_matching_component(self):
        req = self.request_factory(
            path_info="/timeline", args={"component": "contrib.staticfiles"}
        )
        matching = self.make_ticket_event("newticket", "contrib.staticfiles")
        non_matching = self.make_ticket_event("newticket", "contrib.auth")
        _, data, _ = self.filter.post_process_request(
            req, "timeline.rss", {"events": [matching, non_matching]}, {}
        )
        self.assertEqual(data["events"], [matching])

    def test_filters_out_non_ticket_events(self):
        req = self.request_factory(
            path_info="/timeline", args={"component": "contrib.staticfiles"}
        )
        ticket_event = self.make_ticket_event("newticket", "contrib.staticfiles")
        wiki_event = self.make_non_ticket_event("wiki")
        _, data, _ = self.post_process(req, [ticket_event, wiki_event])
        self.assertEqual(data["events"], [ticket_event])

    def test_all_ticket_kinds_match(self):
        req = self.request_factory(
            path_info="/timeline", args={"component": "contrib.staticfiles"}
        )
        events = [
            self.make_ticket_event(kind, "contrib.staticfiles")
            for kind in ("newticket", "editedticket", "closedticket", "reopenedticket")
        ]
        _, data, _ = self.post_process(req, events)
        self.assertEqual(len(data["events"]), 4)

    def test_multiple_components(self):
        req = self.request_factory(
            path_info="/timeline",
            args={"component": ["contrib.staticfiles", "contrib.auth"]},
        )
        matching_staticfiles = self.make_ticket_event(
            "newticket", "contrib.staticfiles"
        )
        matching_auth = self.make_ticket_event("newticket", "contrib.auth")
        non_matching = self.make_ticket_event("newticket", "contrib.admin")
        _, data, _ = self.post_process(
            req, [matching_staticfiles, matching_auth, non_matching]
        )
        self.assertEqual(data["events"], [matching_staticfiles, matching_auth])


class RSTWikiTestCase(SimpleTestCase):
    def test_wiki_can_render_rst(self):
        renderer = Mimeview(EnvironmentStub())
        output = renderer.render(
            content="====\nTEST\n====\n", mimetype="text/x-rst", context=None
        )
        self.assertHTMLEqual(
            str(output),
            '<div class="document" id="test"><h1 class="title">TEST</h1></div>',
        )


class TicketAssignmentValidatorTestCase(SimpleTestCase):
    new_ticket_error = (
        "stage",
        "New tickets must have the Unreviewed triage stage.",
    )
    accept_error = (
        "stage",
        "You cannot accept your own ticket. "
        "Please leave it for another contributor to triage.",
    )
    ready_error = (
        "stage",
        "You cannot mark a ticket assigned to you as ready for checkin. "
        "Please leave it for another contributor to review.",
    )
    unreviewed_error = (
        "owner",
        "Only the ticket's reporter may assign themselves before the "
        "ticket is accepted.",
    )
    limit_error = (
        "owner",
        "You already have 3 or more open, accepted tickets assigned to you. "
        "Please finish or release an existing assignment before taking another "
        "ticket.",
    )

    def setUp(self):
        self.env = EnvironmentStub(
            default_data=True,
            config=[
                ("ticket-custom", "stage", "select"),
                (
                    "ticket-custom",
                    "stage.options",
                    "Unreviewed|Accepted|Ready for checkin|Someday/Maybe",
                ),
                ("ticket-custom", "stage.value", "Unreviewed"),
            ],
        )
        self.addCleanup(self.env.reset_db)
        self.validator = TicketAssignmentValidator(self.env)
        self.permissions = PermissionSystem(self.env)
        self.request = self.make_request("alice")

    def make_request(self, username):
        # Query.count(req) must run with permission to view the tickets.
        self.permissions.grant_permission(username, "TICKET_VIEW")
        return MockRequest(self.env, authname=username)

    def make_ticket(self, *, insert=True, **values):
        ticket = Ticket(self.env)
        ticket.populate(
            {
                "summary": "Test ticket",
                "reporter": "bob",
                "owner": "",
                "status": "new",
                "stage": "Accepted",
                **values,
            }
        )
        if insert:
            ticket.insert()
            # Reload so only subsequent edits appear in ticket._old.
            ticket = Ticket(self.env, ticket.id)
        return ticket

    def make_assignments(self, count, *, owner="alice"):
        for _ in range(count):
            self.make_ticket(owner=owner)

    def test_new_ticket_must_be_unreviewed(self):
        for stage in ("Accepted", "Ready for checkin", "Someday/Maybe"):
            with self.subTest(stage=stage):
                ticket = self.make_ticket(insert=False, reporter="alice", stage=stage)
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket),
                    [self.new_ticket_error],
                )

    def test_new_unreviewed_ticket_allowed(self):
        ticket = self.make_ticket(insert=False, reporter="alice", stage="Unreviewed")
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_new_ticket_self_assignment_allowed_at_limit(self):
        self.make_assignments(3)
        ticket = self.make_ticket(
            insert=False,
            reporter="alice",
            owner="alice",
            stage="Unreviewed",
        )
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_reporter_cannot_accept_own_ticket(self):
        ticket = self.make_ticket(reporter="alice", stage="Unreviewed")
        ticket["stage"] = "Accepted"
        self.assertEqual(
            self.validator.validate_ticket(self.request, ticket),
            [self.accept_error],
        )

    def test_other_user_can_accept_ticket(self):
        ticket = self.make_ticket(stage="Unreviewed")
        ticket["stage"] = "Accepted"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_owner_cannot_mark_ticket_ready_for_checkin(self):
        for new_owner in ("alice", "", "bob"):
            with self.subTest(new_owner=new_owner):
                ticket = self.make_ticket(owner="alice")
                ticket["owner"] = new_owner
                ticket["stage"] = "Ready for checkin"
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket),
                    [self.ready_error],
                )

    def test_cannot_claim_ticket_and_mark_ready_for_checkin(self):
        ticket = self.make_ticket(owner="bob")
        ticket["owner"] = "alice"
        ticket["stage"] = "Ready for checkin"
        self.assertEqual(
            self.validator.validate_ticket(self.request, ticket),
            [self.ready_error],
        )

    def test_other_reviewer_can_mark_ticket_ready_for_checkin(self):
        ticket = self.make_ticket(owner="bob")
        ticket["stage"] = "Ready for checkin"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_unreviewed_ticket_assignment(self):
        for reporter, expected in (
            ("alice", []),
            ("bob", [self.unreviewed_error]),
        ):
            with self.subTest(reporter=reporter):
                ticket = self.make_ticket(reporter=reporter, stage="Unreviewed")
                ticket["owner"] = "alice"
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket), expected
                )

    def test_assignment_limit(self):
        # Validate before each additional assignment is inserted into Trac.
        for existing_count in range(5):
            with self.subTest(existing_count=existing_count):
                ticket = self.make_ticket()
                ticket["owner"] = "alice"
                expected = [] if existing_count < 3 else [self.limit_error]
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket), expected
                )
            self.make_ticket(owner="alice")

    def test_closed_tickets_do_not_count(self):
        self.make_assignments(2)
        self.make_ticket(owner="alice", status="closed", resolution="fixed")
        ticket = self.make_ticket()
        ticket["owner"] = "alice"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_other_triage_stages_do_not_count(self):
        self.make_assignments(2)
        for stage in ("Unreviewed", "Ready for checkin", "Someday/Maybe"):
            self.make_ticket(owner="alice", stage=stage)
        ticket = self.make_ticket()
        ticket["owner"] = "alice"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_other_users_tickets_do_not_count(self):
        self.make_assignments(2)
        self.make_assignments(3, owner="bob")
        ticket = self.make_ticket()
        ticket["owner"] = "alice"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_exempt_groups_can_exceed_assignment_limit(self):
        for group in ("admins", "fellows", "supertriagers"):
            with self.subTest(group=group):
                username = f"member_{group}"
                request = self.make_request(username)
                self.permissions.grant_permission(username, group)
                self.make_assignments(3, owner=username)
                ticket = self.make_ticket()
                ticket["owner"] = username
                self.assertEqual(self.validator.validate_ticket(request, ticket), [])

    def test_exempt_groups_cannot_accept_own_ticket(self):
        for group in ("admins", "fellows", "supertriagers"):
            with self.subTest(group=group):
                username = f"member_{group}"
                request = self.make_request(username)
                self.permissions.grant_permission(username, group)
                ticket = self.make_ticket(reporter=username, stage="Unreviewed")
                ticket["stage"] = "Accepted"
                self.assertEqual(
                    self.validator.validate_ticket(request, ticket),
                    [self.accept_error],
                )

    def test_exempt_groups_cannot_mark_own_ticket_ready_for_checkin(self):
        for group in ("admins", "fellows", "supertriagers"):
            with self.subTest(group=group):
                username = f"member_{group}"
                request = self.make_request(username)
                self.permissions.grant_permission(username, group)
                ticket = self.make_ticket(owner=username)
                ticket["stage"] = "Ready for checkin"
                self.assertEqual(
                    self.validator.validate_ticket(request, ticket),
                    [self.ready_error],
                )

    def test_exempt_groups_cannot_claim_others_unreviewed_ticket(self):
        for group in ("admins", "fellows", "supertriagers"):
            with self.subTest(group=group):
                username = f"member_{group}"
                request = self.make_request(username)
                self.permissions.grant_permission(username, group)
                ticket = self.make_ticket(stage="Unreviewed")
                ticket["owner"] = username
                self.assertEqual(
                    self.validator.validate_ticket(request, ticket),
                    [self.unreviewed_error],
                )

    def test_exempt_groups_must_create_unreviewed_tickets(self):
        for group in ("admins", "fellows", "supertriagers"):
            with self.subTest(group=group):
                username = f"member_{group}"
                request = self.make_request(username)
                self.permissions.grant_permission(username, group)
                ticket = self.make_ticket(insert=False)
                self.assertEqual(
                    self.validator.validate_ticket(request, ticket),
                    [self.new_ticket_error],
                )

    def test_ordinary_edits_allowed(self):
        self.make_assignments(3)
        for reporter, owner, stage in (
            ("alice", "alice", "Accepted"),
            ("bob", "alice", "Ready for checkin"),
            ("bob", "", "Unreviewed"),
            ("bob", "alice", "Unreviewed"),
        ):
            with self.subTest(reporter=reporter, owner=owner, stage=stage):
                ticket = self.make_ticket(reporter=reporter, owner=owner, stage=stage)
                ticket["summary"] = "Updated summary"
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket), []
                )

    def test_releasing_or_assigning_to_others_allowed_at_limit(self):
        self.make_assignments(3)
        for previous_owner in ("alice", "bob"):
            for owner in ("", "bob", "Django Sprints"):
                with self.subTest(previous_owner=previous_owner, owner=owner):
                    ticket = self.make_ticket(owner=previous_owner)
                    ticket["owner"] = owner
                    self.assertEqual(
                        self.validator.validate_ticket(self.request, ticket), []
                    )

    def test_accepting_existing_self_assignment_allowed_at_limit(self):
        self.make_assignments(3, owner="bob")
        ticket = self.make_ticket(owner="bob", stage="Unreviewed")
        ticket["stage"] = "Accepted"
        self.assertEqual(self.validator.validate_ticket(self.request, ticket), [])

    def test_claiming_other_triage_stage_allowed_at_limit(self):
        self.make_assignments(3)
        for stage in ("Ready for checkin", "Someday/Maybe"):
            with self.subTest(stage=stage):
                ticket = self.make_ticket(stage=stage)
                ticket["owner"] = "alice"
                self.assertEqual(
                    self.validator.validate_ticket(self.request, ticket), []
                )
