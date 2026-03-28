#!/bin/bash
set -e

# Expand ${VAR} placeholders in the catalog template using bash.
# The template directory is mounted :ro to prevent credential bleed-back to the host.
# Expanded files are written to /etc/trino/catalog (writable container path).
mkdir -p /etc/trino/catalog
template="$(cat /etc/trino/catalog-template/hive.properties)"
eval "printf '%s\n' \"$template\"" > /etc/trino/catalog/hive.properties

exec /usr/lib/trino/bin/run-trino
