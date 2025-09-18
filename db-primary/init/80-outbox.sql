CREATE SCHEMA IF NOT EXISTS outbox;

CREATE TABLE IF NOT EXISTS outbox.events (
  id           BIGSERIAL PRIMARY KEY,
  event_id     uuid UNIQUE NOT NULL,
  ts           timestamptz NOT NULL,
  entity_type  text NOT NULL,
  entity_id    text NOT NULL,
  event_type   text NOT NULL,
  payload      jsonb NOT NULL,
  actor        text,
  correlation_id uuid,
  causation_id   uuid,
  published_at timestamptz,
  attempts     int NOT NULL DEFAULT 0,
  locked_by    text,
  locked_at    timestamptz
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending
  ON outbox.events (ts) WHERE published_at IS NULL;
