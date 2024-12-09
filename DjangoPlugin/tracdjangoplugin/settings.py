import json
import os

if os.environ.get("SECRETS_FILE"):
    with open(os.environ.get("SECRETS_FILE")) as handle:
        SECRETS = json.load(handle)
else:
    SECRETS = {}

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "djangoproject",
        "USER": "djangoproject",
        "HOST": SECRETS.get("db_host", ""),
        "PORT": SECRETS.get("db_port", 5432),
        "PASSWORD": SECRETS.get("db_password", ""),
    },
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
]


SECRET_KEY = SECRETS.get("secret_key", "")

LOGIN_REDIRECT_URL = "/"

USE_TZ = False
