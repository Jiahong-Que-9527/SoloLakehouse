#!/bin/bash
set -e

# The Trino image does not ship envsubst, so expand the few ${VAR}
# placeholders with bash itself before startup.
template="$(cat /etc/trino/catalog/hive.properties)"
eval "printf '%s\n' \"$template\"" > /tmp/hive.properties
cp /tmp/hive.properties /etc/trino/catalog/hive.properties

exec /usr/lib/trino/bin/run-trino
