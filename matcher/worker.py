import os
import json
import time
import sys
from decimal import Decimal, getcontext

import pika
import psycopg2
from psycopg2.extras import RealDictCursor


getcontext().prec = 28

DB_URL = os.getenv("DATABASE_URL", "postgresql://app:app@db-primary:5432/trading")
AMQP_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE = os.getenv("ORDERS_QUEUE", "orders")



def dbconn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


def D(x):
    return x if isinstance(x, Decimal) else Decimal(str(x))


def log_trade(cur, buyer_id, seller_id, symbol, price, qty, note="match"):
    price = D(price)
    qty = D(qty)
    amount = price * qty

    cur.execute("SELECT name FROM users WHERE id=%s", (buyer_id,))
    buyer_name = cur.fetchone()["name"]
    cur.execute("SELECT name FROM users WHERE id=%s", (seller_id,))
    seller_name = cur.fetchone()["name"]

    cur.execute(
        """
        INSERT INTO public.tx_log(event_type,username,side,symbol,price,qty,amount,note)
        VALUES ('Trade', %s, 'BUY',  %s, %s, %s, %s, %s)
        """,
        (buyer_name, symbol, price, qty, amount, note),
    )
    cur.execute(
        """
        INSERT INTO public.tx_log(event_type,username,side,symbol,price,qty,amount,note)
        VALUES ('Trade', %s, 'SELL', %s, %s, %s, %s, %s)
        """,
        (seller_name, symbol, price, qty, amount, note),
    )



def process_order(payload):
    side = payload["side"].upper()
    user = payload["user"]
    symbol = payload["symbol"]
    price = D(payload["price"])
    qty = D(payload["qty"])

    with dbconn() as c:
        c.set_session(isolation_level="SERIALIZABLE", readonly=False, autocommit=False)
        with c.cursor() as cur:
            cur.execute("SELECT id, balance FROM users WHERE name=%s FOR UPDATE", (user,))
            u = cur.fetchone()
            if not u:
                c.rollback()
                return

            cur.execute(
                """
                INSERT INTO orders(user_id, side, symbol, price, qty, status)
                VALUES (%s, %s, %s, %s, %s, 'NEW')
                RETURNING id
                """,
                (u["id"], side, symbol, price, qty),
            )
            order_id = cur.fetchone()["id"]

            if side == "BUY":
                cur.execute(
                    """
                    SELECT id, user_id, price, qty
                    FROM orders
                    WHERE symbol=%s AND side='SELL' AND status='NEW' AND price <= %s
                    ORDER BY price ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    """,
                    (symbol, price),
                )
                rows = cur.fetchall()
                remain = qty

                for r in rows:
                    if remain <= 0:
                        break

                    r_qty = D(r["qty"])
                    r_px = D(r["price"])
                    trade_qty = remain if remain <= r_qty else r_qty
                    amount = trade_qty * r_px

                    cur.execute(
                        """
                        UPDATE users
                           SET balance = balance - %s
                         WHERE id = %s
                           AND balance >= %s
                        RETURNING id
                        """,
                        (amount, u["id"], amount),
                    )
                    ok = cur.fetchone()
                    if not ok:
                        break

                    cur.execute(
                        """
                        UPDATE positions
                           SET qty = qty - %s
                         WHERE user_id = %s
                           AND symbol = %s
                           AND qty >= %s
                        RETURNING user_id
                        """,
                        (trade_qty, r["user_id"], symbol, trade_qty),
                    )
                    pos_ok = cur.fetchone()
                    if not pos_ok:

                        cur.execute(
                            "UPDATE orders SET status='CANCELLED' WHERE id=%s AND status='NEW'",
                            (r["id"],),
                        )

                        cur.execute(
                            "UPDATE users SET balance = balance + %s WHERE id=%s",
                            (amount, u["id"]),
                        )
                        continue


                    cur.execute(
                        "UPDATE users SET balance = balance + %s WHERE id=%s",
                        (amount, r["user_id"]),
                    )


                    cur.execute(
                        """
                        INSERT INTO positions(user_id, symbol, qty)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, symbol)
                        DO UPDATE SET qty = positions.qty + EXCLUDED.qty
                        """,
                        (u["id"], symbol, trade_qty),
                    )


                    if trade_qty == r_qty:
                        cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (r["id"],))
                    else:
                        cur.execute(
                            "UPDATE orders SET qty = qty - %s WHERE id=%s",
                            (trade_qty, r["id"]),
                        )


                    log_trade(
                        cur,
                        buyer_id=u["id"],
                        seller_id=r["user_id"],
                        symbol=symbol,
                        price=r_px,
                        qty=trade_qty,
                        note=f"match BUY:{order_id} x SELL:{r['id']}",
                    )

                    remain -= trade_qty


                if remain == 0:
                    cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (order_id,))

            else:

                cur.execute(
                    "SELECT qty FROM positions WHERE user_id=%s AND symbol=%s FOR UPDATE",
                    (u["id"], symbol),
                )
                p = cur.fetchone()
                pos = D(p["qty"]) if p else D("0")
                if pos < qty:

                    c.commit()
                    return


                cur.execute(
                    """
                    SELECT id, user_id, price, qty
                    FROM orders
                    WHERE symbol=%s AND side='BUY' AND status='NEW' AND price >= %s
                    ORDER BY price DESC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    """,
                    (symbol, price),
                )
                rows = cur.fetchall()
                remain = qty

                for r in rows:
                    if remain <= 0:
                        break

                    r_qty = D(r["qty"])
                    r_px = D(r["price"])
                    trade_qty = remain if remain <= r_qty else r_qty
                    amount = trade_qty * r_px


                    cur.execute(
                        """
                        UPDATE users
                           SET balance = balance - %s
                         WHERE id = %s
                           AND balance >= %s
                        RETURNING id
                        """,
                        (amount, r["user_id"], amount),
                    )
                    ok = cur.fetchone()
                    if not ok:

                        cur.execute(
                            "UPDATE orders SET status='CANCELLED' WHERE id=%s AND status='NEW'",
                            (r["id"],),
                        )
                        continue


                    cur.execute(
                        """
                        UPDATE positions
                           SET qty = qty - %s
                         WHERE user_id = %s
                           AND symbol = %s
                           AND qty >= %s
                        RETURNING user_id
                        """,
                        (trade_qty, u["id"], symbol, trade_qty),
                    )
                    pos_ok = cur.fetchone()
                    if not pos_ok:


                        cur.execute(
                            "UPDATE users SET balance = balance + %s WHERE id=%s",
                            (amount, r["user_id"]),
                        )
                        break


                    cur.execute(
                        "UPDATE users SET balance = balance + %s WHERE id=%s",
                        (amount, u["id"]),
                    )


                    cur.execute(
                        """
                        INSERT INTO positions(user_id, symbol, qty)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, symbol)
                        DO UPDATE SET qty = positions.qty + EXCLUDED.qty
                        """,
                        (r["user_id"], symbol, trade_qty),
                    )


                    if trade_qty == r_qty:
                        cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (r["id"],))
                    else:
                        cur.execute(
                            "UPDATE orders SET qty = qty - %s WHERE id=%s",
                            (trade_qty, r["id"]),
                        )


                    log_trade(
                        cur,
                        buyer_id=r["user_id"],
                        seller_id=u["id"],
                        symbol=symbol,
                        price=r_px,
                        qty=trade_qty,
                        note=f"match SELL:{order_id} x BUY:{r['id']}",
                    )

                    remain -= trade_qty

                if remain == 0:
                    cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (order_id,))

        c.commit()


def main():
    while True:
        try:
            params = pika.URLParameters(AMQP_URL)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue=QUEUE, durable=True)
            ch.basic_qos(prefetch_count=1)
            print(" [*] matcher started. Waiting for messages...", flush=True)

            def callback(ch_, method, properties, body):
                try:
                    payload = json.loads(body.decode())
                    process_order(payload)
                    ch_.basic_ack(delivery_tag=method.delivery_tag)
                    print(" [x] processed:", payload, flush=True)
                except Exception as e:
                    print(" [!] error:", e, file=sys.stderr, flush=True)
                    time.sleep(0.2)
                    ch_.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            ch.basic_consume(queue=QUEUE, on_message_callback=callback, auto_ack=False)
            ch.start_consuming()
        except Exception as e:
            print(" [!] connection error, retrying:", e, file=sys.stderr, flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
