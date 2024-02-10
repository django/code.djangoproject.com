import os

import trac.web.main

application = trac.web.main.dispatch_request

import django

django.setup()

# Massive hack to make Trac fast, otherwise every git call tries to close ulimit -n (1e6) fds
# Python 3 would perform better here, but we are still on 2.7 for Trac, so leak fds for now.
from tracopt.versioncontrol.git import PyGIT

from .middlewares import DjangoDBManagementMiddleware


application = DjangoDBManagementMiddleware(application)

PyGIT.close_fds = False

trac_dsn = os.getenv("SENTRY_DSN")
if trac_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.wsgi import SentryWsgiMiddleware

    sentry_sdk.init(
        dsn=trac_dsn,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production,
        traces_sample_rate=0.2,
    )
    application = SentryWsgiMiddleware(application)
