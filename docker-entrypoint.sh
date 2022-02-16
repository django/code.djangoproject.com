#!/bin/bash

# Fail loudly, don't echo variables to logs
set -e

# Trac doesn't read environment variables, so allow setting arbitrary lines in
# trac.ini from the environment before Trac starts. E.g.,
#   export TRAC_INI_database = postgres://...
# will become
#   database = postgres://...

for var in "${!TRAC_INI_@}"; do
    sed -i "s;^${var:9} = .*;${var:9} = ${!var};" trac-env/conf/trac.ini
done

if [ "x$TRAC_COLLECT_STATIC" = 'xon' ]; then
    # Collect trac static files to be served by nginx
    /venv/bin/trac-admin ./trac-env/ deploy ./static/
fi

exec "$@"
