FROM apache/hive:4.0.0

USER root
# apache/hive:4.0.0's base image is Debian 11 (bullseye), EOL and no longer
# mirrored with fresh Release signatures — deb.debian.org's bullseye-security
# InRelease expired 2026-09-07 and apt-get update fails without this flag.
# archive.debian.org does not yet carry bullseye-security either (checked
# 2026-09-08: 404), so pointing at the archive is not an option right now.
# Revisit when archive.debian.org picks up bullseye-security, or when the
# base image moves off Debian 11 (that would also touch runtime baseline
# policy in AGENTS.md, so it is a separate decision).
RUN apt-get -o Acquire::Check-Valid-Until=false update \
  && apt-get install -y --no-install-recommends gettext-base netcat-openbsd curl postgresql-client \
  && curl -fsSL -o /opt/hive/lib/postgresql-42.7.3.jar https://jdbc.postgresql.org/download/postgresql-42.7.3.jar \
  && rm -rf /var/lib/apt/lists/*

# Add S3A filesystem JARs (present in Hadoop tools but not on Hive classpath by default)
RUN ln -s /opt/hadoop/share/hadoop/tools/lib/hadoop-aws-3.3.6.jar /opt/hive/lib/ \
 && ln -s /opt/hadoop/share/hadoop/tools/lib/aws-java-sdk-bundle-1.12.367.jar /opt/hive/lib/

COPY metastore-site.xml.template /opt/hive/conf/metastore-site.xml.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
