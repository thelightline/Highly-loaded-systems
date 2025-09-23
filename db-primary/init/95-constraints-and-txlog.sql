ALTER TABLE public.orders
  ALTER COLUMN qty TYPE integer USING ceil(qty)::int,
  ALTER COLUMN qty SET NOT NULL,
  ALTER COLUMN price TYPE numeric(12,2) USING round(price::numeric, 2),
  ALTER COLUMN price SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'orders_qty_check_pos'
  ) THEN
    ALTER TABLE public.orders
      ADD CONSTRAINT orders_qty_check_pos CHECK (qty > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'orders_price_check_pos'
  ) THEN
    ALTER TABLE public.orders
      ADD CONSTRAINT orders_price_check_pos CHECK (price > 0);
  END IF;
END$$;

ALTER TABLE public.positions
  ALTER COLUMN qty TYPE integer USING ceil(qty)::int,
  ALTER COLUMN qty SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'positions_qty_nonneg'
  ) THEN
    ALTER TABLE public.positions
      ADD CONSTRAINT positions_qty_nonneg CHECK (qty >= 0);
  END IF;
END$$;

-- Журнал транзакций
CREATE TABLE IF NOT EXISTS public.tx_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  user_id      int NULL,
  username     text NULL,
  event_type   text NOT NULL,-- OrderPlaced / TradeExecuted / FundsAdded / FundsBlocked / FundsReleased
  side         text NULL,
  symbol       text NULL,
  price        numeric(12,2) NULL,
  qty          integer NULL,
  amount       numeric(14,2) NULL,
  note         text NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_log_ts ON public.tx_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_tx_log_user ON public.tx_log(user_id);
CREATE INDEX IF NOT EXISTS idx_tx_log_symbol ON public.tx_log(symbol);

COMMENT ON TABLE public.tx_log IS 'Журнал транзакций (для UI и аудита бизнес-операций)';
