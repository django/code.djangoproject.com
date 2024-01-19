from urllib.parse import urlparse

from trac.core import Component, implements
from trac.web.chrome import INavigationContributor
from trac.web.api import IRequestFilter, IRequestHandler, RequestDone
from trac.web.auth import LoginModule
from trac.wiki.web_ui import WikiModule
from trac.util.html import tag
from tracext.github import GitHubBrowser

from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils.http import is_safe_url


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


class GitHubBrowserWithSVNChangesets(GitHubBrowser):
    def _format_changeset_link(self, formatter, ns, chgset, label, fullmatch=None):
        # Dead-simple version for SVN changesets.
        if chgset.isnumeric():
            href = formatter.href.changeset(chgset, None, "/")
            return tag.a(label, class_="changeset", href=href)

        # Fallback to the default implementation.
        return super(GitHubBrowserWithSVNChangesets, self)._format_changeset_link(
            formatter, ns, chgset, label, fullmatch
        )


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
        return "plainlogin.html", {
            "form": AuthenticationForm(),
            "next": req.args.get("next", ""),
        }

    def do_post(self, req):
        form = AuthenticationForm(data=req.args)
        if form.is_valid():
            req.environ["REMOTE_USER"] = form.get_user().username
            LoginModule(self.compmgr)._do_login(req)
            req.redirect(self._get_safe_redirect_url(req))
        return "plainlogin.html", {"form": form, "next": req.args.get("next", "")}

    def _get_safe_redirect_url(self, req):
        host = urlparse(req.base_url).hostname
        redirect_url = req.args.get("next", "") or settings.LOGIN_REDIRECT_URL
        if is_safe_url(redirect_url, allowed_hosts=[host]):
            return redirect_url
        else:
            return settings.LOGIN_REDIRECT_URL
