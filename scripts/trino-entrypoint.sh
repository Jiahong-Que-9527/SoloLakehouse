#!/bin/bash
set -e

# Expand ${VAR} placeholders in each catalog template using bash.
# The template directory is mounted :ro to prevent credential bleed-back to the host.
# Expanded files are written to /etc/trino/catalog (writable container path).
mkdir -p /etc/trino/catalog
for template_file in /etc/trino/catalog-template/*.properties; do
  [ -e "$template_file" ] || continue
  base="$(basename "$template_file")"
  template="$(cat "$template_file")"
  eval "printf '%s\n' \"$template\"" > "/etc/trino/catalog/$base"
done

exec /usr/lib/trino/bin/run-trino
