import trac.web.main
application = trac.web.main.dispatch_request

from .djangoauth import DjangoAuth
application = DjangoAuth(application)
