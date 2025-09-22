from urllib.parse import urlparse

from trac.config import ListOption
from trac.core import Component, implements
from trac.web.chrome import INavigationContributor
from trac.web.api import IRequestFilter, IRequestHandler, RequestDone
from trac.web.auth import LoginModule
from trac.wiki.macros import WikiMacroBase
from trac.wiki.web_ui import WikiModule
from trac.util.html import Markup, tag
from tracext.github import GitHubLoginModule, GitHubBrowser

from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils.encoding import iri_to_uri
from django.utils.http import url_has_allowed_host_and_scheme


class MarkupMacro(WikiMacroBase):
    """
    For trusted users (TODO: new/more appropriate permission bit?),
    allow composing interactive HTML inside a Trac Wiki page, to
    facilitate faster iteration on user experiences.

    Example usage in a Trac wiki page:
    {{{#!Markup
    <div id="target">Response code</div>

    <script>
    fetch("/timeline").then(
        resp => document.getElementById("target").innerHTML = resp.status
    );
    </script>
    }}}

    Trac data could be fetched or markup could be rendered server-side
    and called via `args`:
    See https://trac.edgewall.org/wiki/WikiMacros#Macrowitharguments
    """
    def expand_macro(self, formatter, name, content, args=None):
        if "TICKET_EDIT_CC" in formatter.perm:   # supertriagers
            return Markup(content)
        return Markup("<p>Not authorized</p>")  # or raise?


class CustomTheme(Component):
    implements(IRequestFilter)

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, metadata):
        req.chrome["theme"] = "django_theme.html"
        return template, data, metadata


class CustomWikiModule(WikiModule):
    """Works in combination with the CustomNavigationBar and replaces
    the default wiki module.  Has a different logic for active item
    handling.
    """

    def get_active_navigation_item(self, req):
        pagename = req.args.get("page")
        if pagename == "Reports":
            return "custom_reports"
        return "wiki"


class CustomNewTicket(Component):
    """Hide certain options for the new ticket page"""

    implements(IRequestFilter, IRequestHandler)
    hidden_fields = frozenset(
        ["stage", "needs_tests", "needs_docs", "needs_better_patch"]
    )

    def match_request(self, req):
        return req.path_info == "/simpleticket"

    def process_request(self, req):
        req.redirect(req.href.newticket())

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, metadata):
        if data is None:
            data = {}
        if req.path_info == "/newticket" and not data.get("preview_mode", False):
            simple_interface = "TICKET_BATCH_MODIFY" not in req.perm
            if simple_interface and "fields" in data:
                data["fields"] = [
                    f for f in data["fields"] if f["name"] not in self.hidden_fields
                ]
            data["simple_interface"] = simple_interface
            template = "custom_ticket.html"
        return template, data, metadata


class CustomNavigationBar(Component):
    """Implements some more items for the navigation bar."""

    implements(INavigationContributor)

    def get_active_navigation_item(self, req):
        return "custom_reports"

    def get_navigation_items(self, req):
        return [
            (
                "mainnav",
                "custom_reports",
                tag.a("Reports", href=req.href.wiki("Reports")),
            ),
        ]


class CustomSubNavigationBar(Component):
    """Add queue items for the sub navigation bar."""

    implements(INavigationContributor)

    queues = [
        {
            "name": "unreviewed",
            "label": "Needs Triage",
            "params": "stage=Unreviewed&status=!closed&order=changetime&desc=1",
        },
        {
            "name": "needs_patch",
            "label": "Needs Patch",
            "params": "has_patch=0&stage=Accepted&status=!closed&order=changetime&desc=1",
        },
        {
            "name": "needs_pr_review",
            "label": "Needs PR Review",
            "params": (
                "has_patch=1&needs_better_patch=0&needs_docs=0&needs_tests=0&stage=Accepted"
                "&status=!closed&order=changetime&desc=1"
            ),
        },
        {
            "name": "waiting_on_author",
            "label": "Waiting On Author",
            "params": (
                "has_patch=1&needs_better_patch=1&stage=Accepted&status=assigned&status=new"
                "&or&has_patch=1&needs_docs=1&stage=Accepted&status=assigned&status=new"
                "&or&has_patch=1&needs_tests=1&stage=Accepted&status=assigned&status=new"
                "&order=changetime&desc=1"
            ),
        },
        {
            "name": "ready_for_checkin",
            "label": "Ready For Checkin",
            "params": "stage=Ready+for+checkin&status=!closed&order=changetime&desc=1",
        },
    ]

    def get_active_navigation_item(self, req):
        stage = req.args.get("stage")

        if stage == "Unreviewed":
            return "unreviewed"
        if stage == "Ready for checkin":
            return "ready_for_checkin"
        if stage == "Accepted":
            if req.query_string == self.queues[1]["params"]:
                return "needs_patch"
            elif req.query_string == self.queues[2]["params"]:
                return "needs_pr_review"
            elif req.query_string == self.queues[3]["params"]:
                return "waiting_on_author"

        return ""

    def _get_active_class(self, active_item, subnav_name):
        return "active" if active_item == subnav_name else None

    def get_navigation_items(self, req):
        if req.path_info.startswith("/query"):
            active_item = self.get_active_navigation_item(req)
            return [
                (
                    "subnav",
                    queue["name"],
                    tag.a(
                        queue["label"],
                        href="/query?" + queue["params"],
                        class_=self._get_active_class(active_item, queue["name"]),
                    ),
                )
                for queue in self.queues
            ]


class GitHubBrowserWithSVNChangesets(GitHubBrowser):
    def _format_changeset_link(self, formatter, ns, chgset, label, fullmatch=None):
        # Dead-simple version for SVN changesets.
        if chgset.isnumeric():
            href = formatter.href.changeset(chgset, None, "/")
            return tag.a(label, class_="changeset", href=href)

        # Fallback to the default implementation.
        return super()._format_changeset_link(formatter, ns, chgset, label, fullmatch)


class PlainLoginComponent(Component):
    """
    Enable login through a plain HTML form (no more HTTP basic auth)
    """

    implements(IRequestHandler)

    def match_request(self, req):
        return req.path_info == "/login"

    def process_request(self, req):
        if req.method == "POST":
            return self.do_post(req)
        elif req.method == "GET":
            return self.do_get(req)
        else:
            req.send_response(405)
            raise RequestDone

    def do_get(self, req):
        # Not 100% sure why, but for some links (RSS especially) Trac likes
        # to generate URLs pointing to `/login?referer=<the actual link>` when
        # the user is already authenticated.
        if req.is_authenticated:
            req.redirect(self._get_safe_redirect_url(req))
        return "plainlogin.html", {
            "form": AuthenticationForm(),
            "referer": req.args.get("referer", ""),
        }

    def do_post(self, req):
        form = AuthenticationForm(data=req.args)
        if form.is_valid():
            req.environ["REMOTE_USER"] = form.get_user().username
            LoginModule(self.compmgr)._do_login(req)
            req.redirect(self._get_safe_redirect_url(req))
        return "plainlogin.html", {"form": form, "referer": req.args.get("referer", "")}

    def _get_safe_redirect_url(self, req):
        host = urlparse(req.base_url).hostname
        redirect_url = iri_to_uri(req.args.get("referer", ""))

        if not redirect_url:
            redirect_url = settings.LOGIN_REDIRECT_URL
        elif not url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=[host]):
            redirect_url = settings.LOGIN_REDIRECT_URL

        return redirect_url


class ReservedUsernamesComponent(Component):
    """
    Prevents some users from logging in on the website. Useful for example to prevent
    users whose name clashes with a permission group.

    The list of reserved usernames can be configured in trac.ini by specifying
    `reserved.usernames` as a comma-separated list under the [djangoplugin] header.

    If such a user tries to log in, they will be logged out and redirected to the login
    page with a message telling them to choose a different account.
    """

    implements(IRequestFilter)

    reserved_names = ListOption(
        section="djangoplugin",
        name="reserved_usernames",
        default="authenticated",
        doc="A list (comma-separated) of usernames that won't be allowed to log in",
    )

    def pre_process_request(self, req, handler):
        if req.authname in self.reserved_names:
            self.force_logout_and_redirect(req)
        return handler

    def force_logout_and_redirect(self, req):
        component = GitHubLoginModule(self.env)
        # Trac's builtin LoginModule silently ignores logout requests that aren't POST,
        # so we need to be a bit creative here
        req.environ["REQUEST_METHOD"] = "POST"
        try:
            GitHubLoginModule(self.env)._do_logout(req)
        except RequestDone:
            pass  # catch the redirection exception so we can make our own
        req.redirect("/login?reserved=%s" % req.authname)

    def post_process_request(self, req, template, data, metadata):
        return template, data, metadata  # required by Trac to exist
