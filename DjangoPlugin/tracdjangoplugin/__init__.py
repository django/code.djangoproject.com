from trac.core import Component, implements
from trac.web.chrome import INavigationContributor
from trac.web.api import IRequestFilter, IRequestHandler
from trac.wiki.web_ui import WikiModule
from trac.util import Markup
from trac.util.html import tag
from tracext.github import GitHubBrowser


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
                Markup('<a href="%s">Reports</a>' % req.href.wiki("Reports")),
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
