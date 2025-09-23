from fastapi import FastAPI, HTTPException
import os, psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

def db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.on_event("startup")
def init_schema():

    try:
        with db() as c, c.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='products' AND table_name='symbols'
                LIMIT 1
            """)
            exists = cur.fetchone() is not None
            if not exists:

                cur.execute("""
                    CREATE TABLE products.symbols (
                        symbol   TEXT PRIMARY KEY,
                        lot_size NUMERIC(18,6) NOT NULL DEFAULT 1
                    )
                """)
    except Exception as e:
        print(f"[products-service] init skipped: {e}", flush=True)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/symbols")
def list_symbols():
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT symbol, lot_size FROM products.symbols ORDER BY symbol")
        return cur.fetchall()

@app.post("/add_symbol")
def add_symbol(symbol: str, lot_size: int = 1):
    s = (symbol or "").strip().upper()
    if not s or not s.isalnum():
        raise HTTPException(400, "invalid symbol")
    if lot_size <= 0:
        raise HTTPException(400, "lot_size must be positive integer")

    with db() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO products.symbols(symbol, lot_size)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO UPDATE
            SET lot_size = EXCLUDED.lot_size
            RETURNING symbol, lot_size
        """, (s, lot_size))
        row = cur.fetchone()
        return row
