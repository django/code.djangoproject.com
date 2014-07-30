import trac.web.main

from tracdjangoplugin import djangoauth

application = djangoauth.DjangoAuth(trac.web.main.dispatch_request)
