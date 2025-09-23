from fastapi import FastAPI, HTTPException, Body
import os, json, pika, psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
from datetime import datetime
import socket

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
app = FastAPI()

def conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def row_or_404(row, msg="not found"):
    if not row:
        raise HTTPException(404, msg)
    return row

def publish(payload: dict):
    params = pika.URLParameters(RABBITMQ_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue="orders", durable=True)
    ch.basic_publish(
        exchange="",
        routing_key="orders",
        body=json.dumps(payload).encode(),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/time")
def time_now():
    return {"now": datetime.utcnow().isoformat(), "host": socket.gethostname()}

@app.post("/admin/grant_stock")
def admin_grant_stock(user: str, symbol: str, qty: int = Body(..., embed=True)):
    if qty <= 0:
        raise HTTPException(400, "qty must be positive integer")
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM public.users WHERE name=%s", (user,))
        u = row_or_404(cur.fetchone(), "user not found")
        cur.execute("SELECT 1 FROM products.symbols WHERE symbol=%s", (symbol,))
        row_or_404(cur.fetchone(), "symbol not found")
        cur.execute("""
          INSERT INTO public.positions(user_id, symbol, qty)
          VALUES (%s,%s,%s)
          ON CONFLICT (user_id,symbol) DO UPDATE
          SET qty = positions.qty + EXCLUDED.qty
        """, (u["id"], symbol, int(qty)))
    return {"ok": True, "user": user, "symbol": symbol, "delta_qty": int(qty)}

@app.post("/buy")
def buy(user: str, symbol: str, price: float, qty: int):
    if qty <= 0: raise HTTPException(400, "qty must be positive integer")
    if price <= 0: raise HTTPException(400, "price>0")

    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id, balance FROM public.users WHERE name=%s", (user,))
        u = row_or_404(cur.fetchone(), "user not found")
        user_id, balance = u["id"], u["balance"]

        cur.execute("SELECT 1 FROM products.symbols WHERE symbol=%s", (symbol,))
        row_or_404(cur.fetchone(), "symbol not found")

        need = float(price) * int(qty)
        if balance < need:
            raise HTTPException(400, f"insufficient funds: need {need:.2f}, have {balance:.2f}")

    publish({"side":"BUY","user":user,"symbol":symbol,"price":float(price),"qty":int(qty)})
    return {"enqueued": True}

@app.post("/sell")
def sell(user: str, symbol: str, price: float, qty: int):
    if qty <= 0: raise HTTPException(400, "qty must be positive integer")
    if price <= 0: raise HTTPException(400, "price>0")

    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM public.users WHERE name=%s", (user,))
        u = row_or_404(cur.fetchone(), "user not found")
        user_id = u["id"]

        cur.execute("SELECT 1 FROM products.symbols WHERE symbol=%s", (symbol,))
        row_or_404(cur.fetchone(), "symbol not found")

        cur.execute("SELECT COALESCE(qty,0) AS qty FROM public.positions WHERE user_id=%s AND symbol=%s",
                    (user_id, symbol))
        have = cur.fetchone()
        have_qty = int(have["qty"]) if have else 0
        if have_qty < int(qty):
            raise HTTPException(400, f"insufficient position: need {int(qty)}, have {have_qty}")

    publish({"side":"SELL","user":user,"symbol":symbol,"price":float(price),"qty":int(qty)})
    return {"enqueued": True}

@app.get("/orderbook")
def orderbook(symbol: str, depth: int = 10):
    depth = max(1, min(int(depth), 200))
    with db() as c, c.cursor() as cur:
        cur.execute("""
            WITH agg AS (
              SELECT price,
                     SUM(CASE WHEN side='BUY'  THEN qty       ELSE 0 END)::bigint AS buy_qty,
                     SUM(CASE WHEN side='BUY'  THEN qty*price ELSE 0 END)::numeric AS buy_amount,
                     SUM(CASE WHEN side='SELL' THEN qty       ELSE 0 END)::bigint AS sell_qty,
                     SUM(CASE WHEN side='SELL' THEN qty*price ELSE 0 END)::numeric AS sell_amount
              FROM public.orders
              WHERE symbol=%s AND status='NEW'
              GROUP BY price
            )
            SELECT price, buy_qty, buy_amount, sell_qty, sell_amount
            FROM agg
            ORDER BY price DESC
            LIMIT %s
        """, (symbol, depth))
        rows = cur.fetchall()
    return rows

@app.get("/api/transactions")
def transactions(user: Optional[str] = None, symbol: Optional[str] = None, limit: int = 100):
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit must be 1..1000")

    sql = """
      SELECT ts,event_type,username,side,symbol,price,qty,amount,note
      FROM public.tx_log
    """.strip()

    clauses = []
    params = []
    if user:
        clauses.append("username = %s")
        params.append(user)
    if symbol:
        clauses.append("symbol = %s")
        params.append(symbol)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY ts DESC LIMIT %s"
    params.append(limit)

    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows

@app.post("/api/admin/airdrop")
def admin_airdrop(user: str, symbol: str, qty: int):
    if qty <= 0:
        raise HTTPException(400, "qty must be positive integer")
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM public.users WHERE name=%s", (user,))
        u = row_or_404(cur.fetchone(), "user not found")
        cur.execute("SELECT 1 FROM products.symbols WHERE symbol=%s", (symbol,))
        row_or_404(cur.fetchone(), "symbol not found")
        cur.execute("""
          INSERT INTO public.positions(user_id, symbol, qty)
          VALUES (%s,%s,%s)
          ON CONFLICT (user_id, symbol)
          DO UPDATE SET qty = positions.qty + EXCLUDED.qty
          RETURNING qty
        """, (u["id"], symbol, qty))
        new_qty = int(cur.fetchone()["qty"])
    return {"user": user, "symbol": symbol, "qty": new_qty}

@app.get("/user/profile")
def user_profile(name: str):
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT id,name,balance FROM public.users WHERE name=%s", (name,))
        u = row_or_404(cur.fetchone(), "user not found")
        cur.execute("SELECT symbol, qty FROM public.positions WHERE user_id=%s ORDER BY symbol", (u["id"],))
        positions = cur.fetchall()
        try:
            cur.execute("""SELECT ts,event_type,side,symbol,price,qty,amount
                           FROM public.tx_log
                           WHERE username=%s OR user_name=%s
                           ORDER BY ts DESC LIMIT 50""", (name, name))
            recent = cur.fetchall()
        except Exception:
            recent = []
    return {"id": u["id"], "name": u["name"], "balance": float(u["balance"]),
            "positions": positions, "recent": recent}
