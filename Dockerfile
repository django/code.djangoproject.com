# pull official base image
FROM python:3.11-slim-trixie

# set work directory
WORKDIR /code

# set environment varibles
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# getting postgres from PGDG (https://wiki.postgresql.org/wiki/Apt)
# gnupg is required to run apt.postgresql.org.sh
# subversion needed for some of the requirements (welcome to the year 2000)
RUN apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
        git \
        gnupg \
        postgresql-common \
        subversion \
    && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y\
    && apt-get install --assume-yes --no-install-recommends postgresql-client-17\
    && apt-get purge --assume-yes --auto-remove gnupg\
    && apt-get distclean

# install deb packages
RUN apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
        make \
    && apt-get distclean

# install python dependencies
COPY ./requirements.txt ./requirements.txt
COPY ./DjangoPlugin ./DjangoPlugin

RUN apt-get update \
    && apt-get install --assume-yes --no-install-recommends \
        g++ \
        gcc \
        libc6-dev \
        libpq-dev \
    && python3 -m pip install --no-cache-dir -r requirements.txt \
    && apt-get purge --assume-yes --auto-remove \
        gcc \
        libc6-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./docker-entrypoint.sh ./docker-entrypoint.sh
COPY ./Makefile ./Makefile
COPY ./scss ./scss
COPY ./trac-env ./trac-env
RUN make compile-scss
RUN rm -r ./scss


VOLUME /code/trac-env/files/

EXPOSE 9000
ENV DJANGO_SETTINGS_MODULE=tracdjangoplugin.settings TRAC_ENV=/code/trac-env/

ENTRYPOINT ["./docker-entrypoint.sh"]

# Start gunicorn
CMD ["gunicorn", "tracdjangoplugin.wsgi:application", "--bind", "0.0.0.0:9000", "--workers", "8", "--max-requests", "1000"]
