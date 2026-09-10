FROM apache/hive:4.0.0

USER root
# apache/hive:4.0.0 is Debian 11 (bullseye), which is EOL.
# deb.debian.org still publishes a bullseye-security Packages index, but the
# referenced .deb files are being removed from the pool (CI 2026-09-10:
# libcurl4_7.74.0-1.3+deb11u16 404). archive.debian.org still has no
# bullseye-security tree, so we pin apt to archive.debian.org *main* only
# (oldstable packages are enough for gettext/netcat/curl/psql-client at
# image-build time). Revisit when the Hive base image leaves Debian 11
# (runtime-baseline decision) or when archive gains bullseye-security.
RUN set -eux; \
  printf '%s\n' \
    'deb http://archive.debian.org/debian bullseye main' \
    'deb http://archive.debian.org/debian bullseye-updates main' \
    > /etc/apt/sources.list; \
  rm -f /etc/apt/sources.list.d/*; \
  apt-get -o Acquire::Check-Valid-Until=false update; \
  apt-get install -y --no-install-recommends \
    gettext-base netcat-openbsd curl postgresql-client; \
  curl -fsSL -o /opt/hive/lib/postgresql-42.7.3.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.3.jar; \
  rm -rf /var/lib/apt/lists/*

# Add S3A filesystem JARs (present in Hadoop tools but not on Hive classpath by default)
RUN ln -s /opt/hadoop/share/hadoop/tools/lib/hadoop-aws-3.3.6.jar /opt/hive/lib/ \
 && ln -s /opt/hadoop/share/hadoop/tools/lib/aws-java-sdk-bundle-1.12.367.jar /opt/hive/lib/

COPY metastore-site.xml.template /opt/hive/conf/metastore-site.xml.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
