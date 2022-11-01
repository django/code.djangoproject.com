import trac.web.main
application = trac.web.main.dispatch_request

# Massive hack to make Trac fast, otherwise every git call tries to close ulimit -n (1e6) fds
# Python 3 would perform better here, but we are still on 2.7 for Trac, so leak fds for now.
from tracopt.versioncontrol.git import PyGIT
PyGIT.close_fds = False

from .djangoauth import DjangoAuth
application = DjangoAuth(application)
