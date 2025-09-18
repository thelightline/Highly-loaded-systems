-- 1. Схема и таблица для дедупликации event_id
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.event_ids (
  event_id uuid PRIMARY KEY,
  ts       timestamptz NOT NULL
);

-- 2. Партиционированная таблица событий
CREATE TABLE IF NOT EXISTS audit.events (
  ts              timestamptz NOT NULL,                          -- время события
  seq             bigint GENERATED ALWAYS AS IDENTITY,           -- монотонный порядок внутри партиции
  event_id        uuid NOT NULL,                                 -- идемпотентность
  entity_type     text NOT NULL,                                 -- User | Order | Trade | Funds
  entity_id       text NOT NULL,                                 -- user_id / order_id / trade_id (как текст)
  event_type      text NOT NULL CHECK (
                     event_type IN ('UserCreated','FundsAdded','OrderPlaced','TradeExecuted')
                   ),
  payload         jsonb NOT NULL,                                -- полезные поля события
  actor           text NULL,                                     -- источник (api/matcher/etc.)
  correlation_id  uuid NULL,                                     -- для трассировки запроса
  causation_id    uuid NULL,
  PRIMARY KEY (ts, seq)
) PARTITION BY RANGE (ts);

-- Индексы на родителя -> унаследуются в партиции
CREATE INDEX IF NOT EXISTS idx_events_type_ts
  ON audit.events (event_type, ts);
CREATE INDEX IF NOT EXISTS idx_events_entity_ts
  ON audit.events (entity_type, entity_id, ts);

-- DEFAULT-партиция на всякий случай
CREATE TABLE IF NOT EXISTS audit.events_default
  PARTITION OF audit.events DEFAULT;

-- 3. месячные партиции [-12м; +12м] от текущего месяца
DO $$
DECLARE
  d date := date_trunc('month', now())::date - INTERVAL '12 months';
  stop date := date_trunc('month', now())::date + INTERVAL '12 months';
BEGIN
  WHILE d <= stop LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS audit.events_%s
         PARTITION OF audit.events
         FOR VALUES FROM (%L) TO (%L);',
      to_char(d, 'YYYY_MM'),
      d::timestamptz,
      (d + INTERVAL '1 month')::timestamptz
    );
    d := d + INTERVAL '1 month';
  END LOOP;
END $$;
