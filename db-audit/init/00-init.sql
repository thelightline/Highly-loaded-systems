CREATE USER app_audit WITH PASSWORD 'app_audit';
CREATE DATABASE audit OWNER app_audit;
GRANT ALL PRIVILEGES ON DATABASE audit TO app_audit;

\c audit

CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION app_audit;

CREATE TABLE IF NOT EXISTS audit.event_ids (
  event_id uuid PRIMARY KEY,
  ts timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS audit.events (
  ts timestamptz NOT NULL,
  seq bigint GENERATED ALWAYS AS IDENTITY,
  event_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('UserCreated','FundsAdded','OrderPlaced','TradeExecuted')),
  payload jsonb NOT NULL,
  actor text,
  correlation_id uuid,
  causation_id uuid,
  PRIMARY KEY (ts, seq)
) PARTITION BY RANGE (ts);

CREATE INDEX IF NOT EXISTS idx_events_type_ts ON audit.events (event_type, ts);
CREATE INDEX IF NOT EXISTS idx_events_entity_ts ON audit.events (entity_type, entity_id, ts);

CREATE TABLE IF NOT EXISTS audit.events_default PARTITION OF audit.events DEFAULT;

DO $$
DECLARE d date := date_trunc('month', now())::date - INTERVAL '12 months';
        stop date := date_trunc('month', now())::date + INTERVAL '12 months';
BEGIN
  WHILE d <= stop LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS audit.events_%s PARTITION OF audit.events
       FOR VALUES FROM (%L) TO (%L);',
      to_char(d,'YYYY_MM'), d::timestamptz, (d + INTERVAL '1 month')::timestamptz);
    d := d + INTERVAL '1 month';
  END LOOP;
END $$;
