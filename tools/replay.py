# tools/replay.py
import psycopg
from decimal import Decimal

def rebuild(dsn: str, truncate=True):
    with psycopg.connect(dsn) as conn:
        with conn:
            cur = conn.cursor()
            if truncate:
                cur.execute("TRUNCATE TABLE positions RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE TABLE orders RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE")

            cur.execute("""
                SELECT ts, event_type, entity_type, entity_id, payload
                FROM audit.events
                ORDER BY ts, seq
            """)
            for ts, et, ent, eid, payload in cur:
                if et == "UserCreated":
                    cur.execute("INSERT INTO users(id, name, balance) VALUES(%s,%s,0) ON CONFLICT (id) DO NOTHING",
                                (int(eid), payload["name"]))
                elif et == "FundsAdded":
                    cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s",
                                (Decimal(str(payload["amount"])), int(eid)))
                elif et == "OrderPlaced":
                    p = payload
                    cur.execute("""
                      INSERT INTO orders(id,user_id,side,symbol,price,qty,status,created_at)
                      VALUES(%s,%s,%s,%s,%s,%s,'NEW',%s)
                      ON CONFLICT (id) DO NOTHING
                    """, (int(eid), int(p["user_id"]), p["side"], p["symbol"],
                          Decimal(str(p["price"])), Decimal(str(p["qty"])), ts))
                elif et == "TradeExecuted":
                    t = payload
                    cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s",
                                (Decimal(str(t["price"])) * Decimal(str(t["qty"])), int(t["buyer_id"])))
                    cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s",
                                (Decimal(str(t["price"])) * Decimal(str(t["qty"])), int(t["seller_id"])))
                    cur.execute("""
                      INSERT INTO positions(user_id,symbol,qty)
                      VALUES(%s,%s,%s)
                      ON CONFLICT (user_id, symbol) DO UPDATE
                      SET qty = positions.qty + EXCLUDED.qty
                    """, (int(t["buyer_id"]), t["symbol"], Decimal(str(t["qty"]))))
                    cur.execute("""
                      INSERT INTO positions(user_id,symbol,qty)
                      VALUES(%s,%s,%s)
                      ON CONFLICT (user_id, symbol) DO UPDATE
                      SET qty = positions.qty - EXCLUDED.qty
                    """, (int(t["seller_id"]), t["symbol"], Decimal(str(t["qty"]))))

    print("Replay complete.")

if __name__ == "__main__":
    import os
    dsn = os.environ.get("DB_DSN", "postgresql://app:app@localhost:5432/trading")
    rebuild(dsn)
