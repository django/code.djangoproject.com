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
