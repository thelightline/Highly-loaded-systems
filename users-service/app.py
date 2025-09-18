from fastapi import FastAPI, HTTPException, Response
import os, psycopg2, socket
from psycopg2.extras import RealDictCursor
from random import random
from datetime import datetime
from uuid import uuid4

from common.audit import append_outbox

DB_DSN = os.getenv("DATABASE_URL", "host=db-primary dbname=trading user=app password=app port=5432")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "v1")  # v1 | v2
FAIL_RATE = float(os.getenv("FAIL_RATE", "0.0"))      # 0.0..1.0
ACTOR = os.getenv("SERVICE_NAME", "users-service")

app = FastAPI()

def db():
    return psycopg2.connect(DB_DSN, cursor_factory=RealDictCursor)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": SERVICE_VERSION}

@app.get("/time")
def time_now():
    return {"now": datetime.utcnow().isoformat(), "host": socket.gethostname(), "version": SERVICE_VERSION}

@app.post("/create")
def create_user(name: str, balance: float = 0.0, response: Response = None):
    # Response инжектится фреймворком; чтобы не раздражать типизатор:
    if response is None:
        response = Response()
    response.headers["X-Service-Version"] = SERVICE_VERSION
    corr_id = uuid4()

    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.users(name, balance)
            VALUES (%s,%s)
            ON CONFLICT (name) DO NOTHING
            RETURNING id;
        """, (name, balance))
        row = cur.fetchone()
        if not row:
            raise HTTPException(409, "user exists")
        user_id = row["id"]

        append_outbox(
            conn,
            event_type="UserCreated",
            entity_type="User",
            entity_id=str(user_id),
            payload={"name": name, "balance": float(balance)},
            actor=ACTOR,
            correlation_id=corr_id,
        )

        return {"id": user_id, "name": name, "balance": float(balance)}

@app.post("/add_funds")
def add_funds(name: str, amount: float, reason: str | None = None, response: Response = None):
    if amount <= 0:
        raise HTTPException(400, "amount>0")
    if response is None:
        response = Response()
    response.headers["X-Service-Version"] = SERVICE_VERSION
    if SERVICE_VERSION == "v2" and FAIL_RATE > 0 and random() < FAIL_RATE:
        raise HTTPException(500, "v2 injected failure")

    corr_id = uuid4()

    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE public.users
               SET balance = balance + %s
             WHERE name = %s
         RETURNING id, balance;
        """, (amount, name))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "user not found")
        user_id, new_balance = row["id"], row["balance"]

        append_outbox(
            conn,
            event_type="FundsAdded",
            entity_type="User",
            entity_id=str(user_id),
            payload={"amount": float(amount), "reason": reason},
            actor=ACTOR,
            correlation_id=corr_id,
        )

        return {"id": user_id, "balance": float(new_balance)}

@app.get("/balance")
def balance(name: str, response: Response):
    response.headers["X-Service-Version"] = SERVICE_VERSION
    if SERVICE_VERSION == "v2" and FAIL_RATE > 0 and random() < FAIL_RATE:
        raise HTTPException(500, "v2 injected failure")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, balance FROM public.users WHERE name=%s", (name,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "user not found")
        return {"id": row["id"], "name": row["name"], "balance": float(row["balance"])}
