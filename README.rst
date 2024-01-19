Configuration for Django's Trac instance (code.djangoproject.com)
=================================================================

Local install
-------------

Getting a local Trac install running is a bit tricky. Here are a few tricks
that can help:

* Follow the installation instructions in djangoproject/README.rst (especially
  the database creation).
* Use ``trac-admin ./trac-env/ permission add anonymous TRAC_ADMIN``
  to give all permissions to the anonymous user.
* Use the command ``DJANGO_SETTINGS_MODULE=tracdjangoplugin.settings TRAC_ENV=`pwd`/trac-env gunicorn tracdjangoplugin.wsgi:application --bind 0.0.0.0:9000 --workers=1 --reload`` to serve Trac locally.
* If you've modified the ``trackhack.scss`` file, use
  ``sassc scss/trachacks.scss trac-env/htdocs/css/trachacks.css -s compressed``
  to compile it to CSS.

Using Docker
------------

* Install Docker
* ``pip install docker-compose``
* Create a ``secrets.json`` file at the root of the repository (next to `Dockerfile`), containing
  something like::

    {
      "secret_key": "xyz",
      "db_host": "localhost",
      "db_password": "secret"
    }

* ``docker-compose up --build``
* Follow instructions above to create/load the DB, grant permissions, create the
  config, etc. For example::

    docker-compose up --build
    export DATABASE_URL=postgres://code.djangoproject:secret@db/code.djangoproject
    docker-compose exec -T db psql $DATABASE_URL < ../djangoproject.com/tracdb/trac.sql
    docker-compose exec trac trac-admin /code/trac-env/ permission add anonymous TRAC_ADMIN

Using Podman
------------

It may be possible to use Podman for local development to more closely simulate
production. The above Docker instructions should work for Podman as well,
however, be aware that ``podman-compose`` is not as well battle-tested as
``docker-compose`` (e.g., it may require pruning or forcefully stopping a
container before it will rebuild properly).

How to port the CSS from djangoproject.com
------------------------------------------

Assumes that `code.djangoproject.com` and `djangoproject.com` are stored in the
same directory (adjust paths if needed).

1. Copy the generated CSS:
   ``cp ../djangoproject.com/static/css/*.css trac-env/htdocs/css/``
2. Copy _utils.scss (needed by trackahacks.scss):
   ``cp ../djangoproject.com/static/scss/_utils.scss scss/``
3. Copy the javascript directory:
   ``cp -rT ../djangoproject.com/static/js trac-env/htdocs/js``
4. Compile trackhacks.scss:
   ``make compile-scss``

How to recreate `trac.sql` after upgrading Trac
-----------------------------------------------


Start with a clean slate::

  docker-compose down
  sh -c 'cd ../djangoproject.com && git checkout tracdb/trac.sql'

Bring up database and Trac via docker-compose::

  docker-compose up --build -d
  export DATABASE_URL=postgres://code.djangoproject:secret@db/code.djangoproject
  docker-compose exec -T db psql $DATABASE_URL < ../djangoproject.com/tracdb/trac.sql
  docker-compose exec trac /venv/bin/trac-admin /code/trac-env/ upgrade
  docker-compose exec db pg_dump --column-inserts -d $DATABASE_URL > ../djangoproject.com/tracdb/trac.sql


Note:

* There's no need to run the ``trac-admin ... wiki upgrade`` command
* Be careful with changes that ``trac-admin ... upgrade`` makes to
  ``trac.ini``. We usually don't want them.
* Review the diff carefully to make sure no unexpected database changes
  are inadvertently included.
