#!/bin/sh
set -e

echo "Waiting for primary db-primary:5432 to be ready..."
until PGPASSWORD=repl pg_isready -h db-primary -p 5432 -U repl >/dev/null 2>&1; do
  sleep 1
done
echo "Primary is ready."

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Cloning replica1 from primary via slot..."
  PGPASSWORD=repl pg_basebackup -h db-primary -U repl -D "$PGDATA" \
    -Fp -Xs -R -P -S replica1_slot
  echo "primary_conninfo = 'host=db-primary user=repl password=repl application_name=replica1'" >> "$PGDATA/postgresql.auto.conf"
  echo "primary_slot_name = 'replica1_slot'" >> "$PGDATA/postgresql.auto.conf"
fi

echo "hot_standby = on" >> "$PGDATA/postgresql.conf"

exec docker-entrypoint.sh postgres
