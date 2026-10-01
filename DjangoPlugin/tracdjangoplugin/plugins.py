import http.client
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils.encoding import iri_to_uri
from django.utils.http import url_has_allowed_host_and_scheme
from trac.config import ListOption
from trac.core import Component, implements
from trac.util.html import Markup, tag
from trac.web.api import IRequestFilter, IRequestHandler, RequestDone
from trac.web.auth import LoginModule
from trac.web.chrome import INavigationContributor
from trac.wiki.web_ui import WikiModule
from tracext.github import GitHubBrowser, GitHubLoginModule

from DjangoPlugin.tracdjangoplugin.settings import SECRETS


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


class TimelineTicketComponentFilter(Component):
    """Filter timeline events to only show tickets for a given ticket component.

    Activated when the request includes a ``component`` query argument, e.g.
    /timeline?component=contrib.staticfiles&format=rss

    Non-ticket events (wiki edits, commits, milestones, attachments) are
    hidden when ``component`` is set.

    ``batchmodify`` events are excluded because a single batch operation may
    span multiple ticket components, making it ambiguous which filter to apply.
    """

    implements(IRequestFilter)

    _TICKET_COMPONENT_INDEX = 8  # see trac/ticket/web_ui.py produce_event()
    _TICKET_KINDS = frozenset(
        ["newticket", "editedticket", "closedticket", "reopenedticket"]
    )

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, metadata):
        if req.path_info != "/timeline" or data is None:
            return template, data, metadata
        components = set(req.args.getlist("component"))
        if not components:
            return template, data, metadata
        data["events"] = [
            event
            for event in data["events"]
            if event["kind"] in self._TICKET_KINDS
            and event["data"][self._TICKET_COMPONENT_INDEX] in components
        ]
        return template, data, metadata


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


class GithubStatusComponent(Component):
    # Examples:
    #     https://code.djangoproject.com/ticket/34976 - multiple open prs, false positive build
    #     https://code.djangoproject.com/ticket/29898 - 9 prs
    #     https://code.djangoproject.com/ticket/26220 - waiting on author, no open PRs
    #     https://code.djangoproject.com/ticket/13539 - no PR
    #     https://github.com/django/django/pull/22040 - draft PR

    BUILD_ICONS = {
        "success": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-label="Checks OK" viewBox="0 0 16 16" width="16" height="16"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg>',
        "failure": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-label="Checks failed" viewBox="0 0 16 16" width="16" height="16"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path></svg>',
    }

    STATE_ICONS = {
        "open": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16" width="16" height="16"><path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"></path></svg>',
        "draft": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16" width="16" height="16"><path d="M3.25 1A2.25 2.25 0 0 1 4 5.372v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.251 2.251 0 0 1 3.25 1Zm9.5 14a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5ZM2.5 3.25a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0ZM3.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm9.5 0a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM14 7.5a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0Zm0-4.25a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0Z"></path></svg>',
        "closed": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16" width="16" height="16"><path d="M3.25 1A2.25 2.25 0 0 1 4 5.372v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.251 2.251 0 0 1 3.25 1Zm9.5 5.5a.75.75 0 0 1 .75.75v3.378a2.251 2.251 0 1 1-1.5 0V7.25a.75.75 0 0 1 .75-.75Zm-2.03-5.273a.75.75 0 0 1 1.06 0l.97.97.97-.97a.748.748 0 0 1 1.265.332.75.75 0 0 1-.205.729l-.97.97.97.97a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-.97-.97-.97.97a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734l.97-.97-.97-.97a.75.75 0 0 1 0-1.06ZM2.5 3.25a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0ZM3.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm9.5 0a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z"></path></svg>',
        "merged": '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16" width="16" height="16"><path d="M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z"></path></svg>',
    }

    STATE_COLORS = {
        "open": "green",
        "draft": "grey",
        "closed": "red",
        "merged": "purple",
    }

    implements(IRequestFilter)

    def match_request(self, req):
        return req.path_info == "/ticket"

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, metadata):
        if template != "ticket.html" or not data or "fields" not in data:
            return template, data, metadata

        ticket_id = req.path_info.rsplit("/", 1)[-1]

        # Fetch PR info about this ticket from github.
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GITHUB_PR_TOKEN}",
        }
        body = {
            "query": """
                query($searchQuery: String!) {
                    search(query: $searchQuery, type: ISSUE, first: 50) {
                        edges {
                            node {
                                ... on PullRequest {
                                    number title state isDraft updatedAt commits(last: 1) {
                                        nodes {
                                            commit {
                                                oid statusCheckRollup {
                                                    state
                                                }
                                            }
                                        }
                                    }
                                    comments(last: 50) {
                                        nodes {
                                            body
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                """,
            "variables": {
                "searchQuery": "repo:django/django is:pr in:title "
                f'"#{ticket_id} " OR "#{ticket_id}," OR "#{ticket_id}:" OR '
                f'"#{ticket_id})"'
            },
        }

        rendered = ""
        try:
            response = requests.post(
                "https://api.github.com/graphql", json=body, headers=headers, timeout=5
            )

            status_str = response.json().get("status")
            if status_str == None:
                rendered = self._process_response(response)
            else:
                rendered = Markup(
                    f"<span>Error: {http.client.responses[int(status_str)]}</span>"
                )
        except requests.Timeout:
            rendered = Markup(f"<span>Error: Timeout</span>")
        except requests.ConnectionError:
            rendered = Markup(f"<span>Error: Connection error</span>")
        except Exception:
            rendered = Markup(f"<span>Error: Undefined error</span>")

        data["fields"].append(
            {
                "name": "github_pr_status",
                "label": "Pull Requests 🚀",
                "type": "text",
                "custom": True,
                "skip": False,
                "rendered": rendered,  # or rendered_column for a different look.
            }
        )

        return template, data, metadata  # required by Trac to exist

    def _process_response(self, response):
        rendered = ""
        lis = ""
        prs = response.json().get("data", {}).get("search", {}).get("edges", [])
        if len(prs) > 0:
            for pr in prs:
                print(pr)
                state = pr.get("node", {}).get("state", "").lower()
                if state == "open" and pr.get("node", {}).get("isDraft", False):
                    state = "draft"
                number = pr.get("node", {}).get("number", "")
                pr_url = f"https://github.com/django/django/issues/{number}"
                status_check_rollup = (
                    next(
                        iter(pr.get("node", {}).get("commits", {}).get("nodes", [])), {}
                    )
                    .get("commit", {})
                    .get("statusCheckRollup", None)
                )
                print(status_check_rollup)
                build = (status_check_rollup or {}).get("state", "").lower() or None

                state_icon = self.STATE_ICONS.get(state, "")

                build_icon = self.BUILD_ICONS.get(build, "") if build else None

                if build_icon is not None:
                    lis += f"""
                        <li aria-label="{state} pull request {number} build {build}">
                            <span class="pr-{state}" aria-hidden="true">{state_icon}</span>
                            <a href="{pr_url}">{number}</a>
                            <span class="build-{build}" aria-hidden="true">{build_icon}</span>
                        </li>
                    """
                else:
                    lis += f"""
                        <li aria-label="{state} pull request {number}">
                            <span class="pr-{state}" aria-hidden="true">{state_icon}</span>
                            <a href="{pr_url}">{number}</a>
                        </li>
                    """

            rendered = Markup(
                f'<ul class="github-pr-list" aria-label="Pull requests">{lis}</ul>'
            )
        else:
            rendered = Markup(
                '<a href="https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/working-with-git/#publishing-work">How to create a pull request</a>'
            )

        return rendered
