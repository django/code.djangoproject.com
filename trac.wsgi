import json
import os

import trac.web.main
application = trac.web.main.dispatch_request

# Add GitHub authentication
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'oauth2-secrets.json')) as f:
    oauth2_secrets = json.loads(f.read())
oauth2_secrets = dict((str(k), str(v)) for (k, v) in oauth2_secrets.items())

from wsgioauth2 import github
oauth2_client = github.make_client(client_id=oauth2_secrets['client_id'], client_secret=oauth2_secrets['client_secret'])

application = oauth2_client.wsgi_middleware(application, path='/oauth2/', login_path='/login', set_remote_user=True, secret=oauth2_secrets['hmac_secret'])
