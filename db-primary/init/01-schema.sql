CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  balance NUMERIC(18,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  qty NUMERIC(18,6) NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id),
  side TEXT CHECK (side IN ('BUY','SELL')),
  symbol TEXT NOT NULL,
  price NUMERIC(18,6) NOT NULL,
  qty NUMERIC(18,6) NOT NULL,
  status TEXT NOT NULL DEFAULT 'NEW',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_active
  ON orders (symbol, side, price, created_at)
  WHERE status='NEW';

INSERT INTO users (name, balance) VALUES ('alice', 100000.00) ON CONFLICT DO NOTHING;
INSERT INTO users (name, balance) VALUES ('bob',   100000.00) ON CONFLICT DO NOTHING;
