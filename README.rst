Configuration for Django's Trac instance (code.djangoproject.com)
=================================================================

Local install
-------------

Getting a local Trac install running is a bit tricky. Here are a few tricks
that can help:

* Install the requirements in the same virtualenv as djangoproject.com.
* Follow the installation instructions in djangoproject/README.rst (especially
  the database creation).
* Use ``psql -U code.djangoproject -d code.djangoproject -c "INSERT INTO permission (username, action) VALUES ('anonymous', 'TRAC_ADMIN')"``
  to give all permissions to the anonymous user.
* Use the command ``tracd --port 9000 -s trac-env`` to serve Trac locally.
* If you've modified the ``trackhack.scss`` file, use
  ``sassc trac-env/htdocs/css/trachacks.scss trac-env/htdocs/css/trachacks.css -s compressed``
  to compile it to CSS.

How to port the CSS from djangoproject.com
------------------------------------------

Assumes that `code.djangoproject.com` and `djangoproject.com` are stored in the
same directory (adjust paths if needed).

1. Copy the generated CSS:
   ``cp ../djangoproject.com/static/css/*.css trac-env/htdocs/css/``
2. Copy _utils.scss (needed by trackahacks.scss):
   ``cp ../djangoproject.com/static/scss/_utils.scss trac-env/htdocs/css/``
3. Copy the javascript directory:
   ``cp -rT ../djangoproject.com/static/js trac-env/htdocs/js``
4. Compile trackhacks.scss:
   ``sassc trac-env/htdocs/css/trachacks.scss trac-env/htdocs/css/trachacks.css -s compressed``
