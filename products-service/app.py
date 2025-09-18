from fastapi import FastAPI, HTTPException
import os, psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

def conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.post("/symbols/create")
def create_symbol(symbol: str, lot_size: float = 1.0):
    with conn() as c, c.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS products (symbol TEXT PRIMARY KEY, lot_size NUMERIC(18,6) NOT NULL DEFAULT 1)")
        cur.execute("INSERT INTO products(symbol, lot_size) VALUES (%s,%s) ON CONFLICT (symbol) DO NOTHING RETURNING symbol;", (symbol, lot_size))
        row = cur.fetchone()
        if not row: raise HTTPException(409, "symbol exists")
        return {"symbol": row["symbol"], "lot_size": lot_size}

@app.get("/symbols")
def list_symbols():
    with conn() as c, c.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS products (symbol TEXT PRIMARY KEY, lot_size NUMERIC(18,6) NOT NULL DEFAULT 1)")
        cur.execute("SELECT symbol, lot_size FROM products ORDER BY symbol")
        return cur.fetchall()

with conn:
    # итоги сделки:
    trade = {
      "symbol": symbol, "price": float(price), "qty": float(qty),
      "buy_order_id": int(buy_id), "sell_order_id": int(sell_id),
      "buyer_id": int(buyer_id), "seller_id": int(seller_id)
    }
    append_outbox(conn,
        event_type="TradeExecuted",
        entity_type="Trade",
        entity_id=str(trade_id),
        payload=trade,
        actor="matcher",
        correlation_id=req_id,
        causation_id=order_event_id_if_any)
