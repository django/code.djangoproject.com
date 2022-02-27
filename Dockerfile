# The official python:2.7 image no longer receives automatic rebuilds (it's
# a year old as of October, 2021), so use the latest LTS release of Ubuntu
# that includes Python 2.7 instead.
FROM ubuntu:20.04

# Install packages needed to run your application (not build deps).
RUN set -x \
    && RUN_DEPS=" \
    ca-certificates \
    git \
    libpq5 \
    make \
    postgresql-client \
    python2.7 \
    " \
    && apt-get update && apt-get install -y --no-install-recommends $RUN_DEPS \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
ADD requirements.txt /requirements.txt
ADD DjangoPlugin /DjangoPlugin

# Install build deps, then run `pip install`, then remove unneeded build deps all in a single step.
# Correct the path to your production requirements file, if needed.
# For installing a python2.7-compatible pip: https://stackoverflow.com/a/54335642/166053
# Since we are using the system Python, also isolate the code in its own virtualenv.
RUN set -x \
    && BUILD_DEPS=" \
    build-essential \
    libpq-dev \
    python2.7-dev \
    wget \
    " \
    && apt-get update && apt-get install -y --no-install-recommends $BUILD_DEPS \
    && wget -q -O /tmp/get-pip.py https://bootstrap.pypa.io/pip/2.7/get-pip.py \
    && python2.7 /tmp/get-pip.py \
    && rm /tmp/get-pip.py \
    && python2.7 -m pip install virtualenv \
    && virtualenv /venv \
    && /venv/bin/python -m pip install --no-cache-dir -r /requirements.txt \
    \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false $BUILD_DEPS \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
RUN mkdir /code/
WORKDIR /code/
ADD . /code/

RUN PATH=/venv/bin:${PATH} make compile-scss

VOLUME /code/trac-env/files/

# gunicorn or tracd will listen on this port
EXPOSE 9000

ENV DJANGO_SETTINGS_MODULE=tracdjangoplugin.settings TRAC_ENV=/code/trac-env/

ENTRYPOINT ["/code/docker-entrypoint.sh"]

# Start gunicorn
CMD ["/venv/bin/gunicorn", "tracdjangoplugin.wsgi:application", "--bind", "0.0.0.0:9000", "--workers", "4", "--max-requests", "1000"]
