from fastapi import FastAPI, HTTPException
import os
import json
import socket
from datetime import datetime

import pika
import psycopg2
from psycopg2.extras import RealDictCursor

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://app:app@db-primary:5432/trading")

app = FastAPI()

def db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"db error: {e}")

@app.get("/time")
def time_now():
    return {"now": datetime.utcnow().isoformat(), "host": socket.gethostname()}

def _ensure_user_and_symbol(cur, user: str, symbol: str) -> int:
    cur.execute("SELECT id FROM public.users WHERE name=%s", (user,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "user not found")
    user_id = int(row["id"])

    cur.execute("SELECT to_regclass('products.symbols') IS NOT NULL AS exists")
    exists_products_schema = bool(list(cur.fetchone().values())[0])

    if exists_products_schema:
        cur.execute("SELECT 1 FROM products.symbols WHERE symbol=%s", (symbol,))
    else:
        cur.execute("SELECT 1 FROM public.products WHERE symbol=%s", (symbol,))

    if not cur.fetchone():
        raise HTTPException(404, "symbol not found")

    return user_id

    return user_id

def _append_outbox(conn, *, event_type, entity_type, entity_id, payload, actor="backend"):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO outbox.events(event_id, ts, entity_type, entity_id, event_type, payload, actor)
            VALUES (gen_random_uuid(), now(), %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (entity_type, entity_id, event_type, json.dumps(payload), actor),
        )

@app.post("/buy")
def buy(user: str, symbol: str, price: float, qty: float):
    if qty <= 0 or price <= 0:
        raise HTTPException(400, "qty/price>0")

    with db() as conn, conn.cursor() as cur:
        user_id = _ensure_user_and_symbol(cur, user, symbol)
        cur.execute(
            """
            INSERT INTO public.orders(user_id, side, symbol, price, qty, status)
            VALUES (%s, 'BUY', %s, %s, %s, 'NEW')
            RETURNING id
            """,
            (user_id, symbol, price, qty),
        )
        order_id = str(cur.fetchone()["id"])
        _append_outbox(
            conn,
            event_type="OrderPlaced",
            entity_type="Order",
            entity_id=order_id,
            payload={"user_id": user_id, "side": "BUY", "symbol": symbol,
                     "price": float(price), "qty": float(qty)},
            actor="backend",
        )

    publish({"side": "BUY", "user": user, "symbol": symbol, "price": price, "qty": qty})
    return {"enqueued": True, "order_id": order_id}

@app.post("/sell")
def sell(user: str, symbol: str, price: float, qty: float):
    if qty <= 0 or price <= 0:
        raise HTTPException(400, "qty/price>0")

    with db() as conn, conn.cursor() as cur:
        user_id = _ensure_user_and_symbol(cur, user, symbol)
        cur.execute(
            """
            INSERT INTO public.orders(user_id, side, symbol, price, qty, status)
            VALUES (%s, 'SELL', %s, %s, %s, 'NEW')
            RETURNING id
            """,
            (user_id, symbol, price, qty),
        )
        order_id = str(cur.fetchone()["id"])
        _append_outbox(
            conn,
            event_type="OrderPlaced",
            entity_type="Order",
            entity_id=order_id,
            payload={"user_id": user_id, "side": "SELL", "symbol": symbol,
                     "price": float(price), "qty": float(qty)},
            actor="backend",
        )

    publish({"side": "SELL", "user": user, "symbol": symbol, "price": price, "qty": qty})
    return {"enqueued": True, "order_id": order_id}
