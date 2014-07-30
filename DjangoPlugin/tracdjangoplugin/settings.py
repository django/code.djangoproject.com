import json
import os

# It's a secret to everybody
with open(os.environ.get('SECRETS_FILE')) as handle:
    SECRETS = json.load(handle)

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'djangoproject',
        'USER': 'djangoproject',
        'HOST': SECRETS.get('db_host', 'localhost'),
        'PASSWORD': SECRETS.get('db_password', ''),
    },
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
]


SECRET_KEY = str(SECRETS['secret_key'])
BASIC_AUTH_REALM="Django's Trac"
