#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 -U postgres -d trading -f /docker-entrypoint-initdb.d/01-schema.sql


psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "SELECT pg_create_physical_replication_slot('replica1_slot') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name='replica1_slot');"
psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "SELECT pg_create_physical_replication_slot('replica2_slot') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name='replica2_slot');"
