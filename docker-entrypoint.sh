#!/bin/sh

# Trac doesn't read environment variables, so add DATABASE_URL to trac.ini
# before it starts.
sed -i "s;^database = .*;database = ${DATABASE_URL};" trac-env/conf/trac.ini

exec "$@"
