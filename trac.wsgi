import json
import os
import sys
import site

SITE_PACKAGES = '/home/trac/venv/lib/python2.6/site-packages'

# Write stdout to stderr
sys.stdout = sys.stderr

# Remember original sys.path.
prev_sys_path = list(sys.path)

# Add each new site-packages directory.
site.addsitedir(SITE_PACKAGES)

# Reorder sys.path so new directories at the front.
new_sys_path = []
for item in list(sys.path):
    if item not in prev_sys_path:
        new_sys_path.append(item)
        sys.path.remove(item)
sys.path[:0] = new_sys_path

# Bootstrap Trac
os.environ['TRAC_ENV'] = os.path.abspath(os.path.join(os.path.dirname(__file__), "trac-env"))
os.environ['PYTHON_EGG_CACHE'] = '/var/cache/python-egg-cache'

import trac.web.main
application = trac.web.main.dispatch_request

# Add GitHub authentication
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'oauth2-secrets.json')) as f:
    oauth2_secrets = json.loads(f.read())
oauth2_secrets = dict((str(k), str(v)) for (k, v) in oauth2_secrets.items())

from wsgioauth2 import github
oauth2_client = github.make_client(client_id=oauth2_secrets['client_id'], client_secret=oauth2_secrets['client_secret'])

application = oauth2_client.wsgi_middleware(application, path='/oauth2/', login_path='/login', set_remote_user=True, secret=oauth2_secrets['hmac_secret'])
