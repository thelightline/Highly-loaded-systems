from fastapi import FastAPI, HTTPException
import os, psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")
app = FastAPI()

def conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.post("/create")
def create_user(name: str, balance: float = 0.0):
    with conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO public.users(name, balance) VALUES (%s,%s) ON CONFLICT (name) DO NOTHING RETURNING id;", (name,balance))
        row = cur.fetchone()
        if not row:
            raise HTTPException(409, "user exists")
        return {"id": row["id"], "name": name, "balance": balance}

@app.post("/add_funds")
def add_funds(name: str, amount: float):
    if amount <= 0: raise HTTPException(400, "amount>0")
    with conn() as c, c.cursor() as cur:
        cur.execute("UPDATE public.users SET balance = balance + %s WHERE name=%s RETURNING id, balance;", (amount, name))
        row = cur.fetchone()
        if not row: raise HTTPException(404, "user not found")
        return {"id": row["id"], "balance": row["balance"]}

@app.get("/balance")
def balance(name: str):
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, name, balance FROM public.users WHERE name=%s", (name,))
        row = cur.fetchone()
        if not row: raise HTTPException(404, "user not found")
        return row

with conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users(name,balance) VALUES(%s,0) RETURNING id", (name,))
        user_id = str(cur.fetchone()[0])
    append_outbox(conn,
        event_type="UserCreated",
        entity_type="User",
        entity_id=user_id,
        payload={"name": name},
        actor="users-service",
        correlation_id=req_id)

with conn:
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user_id))
    append_outbox(conn,
        event_type="FundsAdded",
        entity_type="User",
        entity_id=str(user_id),
        payload={"amount": float(amount), "reason": reason},
        actor="users-service",
        correlation_id=req_id)
