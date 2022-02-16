#!/bin/bash

# Trac doesn't read environment variables, so allow setting arbitrary lines in
# trac.ini from the environment before Trac starts. E.g.,
#   export TRAC_INI_database = postgres://...
# will become
#   database = postgres://...

for var in "${!TRAC_INI_@}"; do
    sed -i "s;^${var:9} = .*;${var:9} = ${!var};" trac-env/conf/trac.ini
done

exec "$@"
