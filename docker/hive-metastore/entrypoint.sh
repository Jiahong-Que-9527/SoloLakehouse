#!/bin/bash
set -euo pipefail

envsubst < /opt/hive/conf/metastore-site.xml.template > /opt/hive/conf/metastore-site.xml

schematool -dbType postgres -initSchemaTo 4.0.0 || true

exec hive --service metastore
