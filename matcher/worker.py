import os, json, time, sys, socket
import pika, psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal, getcontext

getcontext().prec = 28

DB_URL = os.getenv("DATABASE_URL", "postgresql://app:app@db-primary:5432/trading")
AMQP_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE = os.getenv("ORDERS_QUEUE", "orders")

def dbconn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def D(x):
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))

def process_order(payload):
    side = payload["side"].upper()
    user = payload["user"]
    symbol = payload["symbol"]
    price = D(payload["price"])
    qty   = D(payload["qty"])

    with dbconn() as c:
        c.set_session(isolation_level="SERIALIZABLE", readonly=False, autocommit=False)
        with c.cursor() as cur:
            # user
            cur.execute("SELECT id,balance FROM users WHERE name=%s FOR UPDATE", (user,))
            u = cur.fetchone()
            if not u:
                return

            # создать свой ордер (NEW)
            cur.execute("""
                INSERT INTO orders(user_id, side, symbol, price, qty, status)
                VALUES (%s,%s,%s,%s,%s,'NEW') RETURNING id
            """, (u["id"], side, symbol, price, qty))
            order_id = cur.fetchone()["id"]

            if side == "BUY":
                cost = price * qty
                bal  = D(u["balance"])
                if bal < cost:
                    # денег нет — оставим NEW
                    return

                # встречные SELL с ценой <= нашей
                cur.execute("""
                  SELECT id,user_id,price,qty FROM orders
                  WHERE symbol=%s AND side='SELL' AND status='NEW' AND price<=%s
                  ORDER BY price ASC, created_at ASC
                  FOR UPDATE SKIP LOCKED
                """, (symbol, price))
                rows = cur.fetchall()
                remain = qty
                for r in rows:
                    if remain <= 0: break
                    r_qty = D(r["qty"])
                    r_px  = D(r["price"])
                    trade_qty = remain if remain <= r_qty else r_qty
                    amount = trade_qty * r_px

                    # списать деньги у покупателя
                    cur.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, u["id"]))
                    # начислить продавцу
                    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, r["user_id"]))
                    # позиции
                    cur.execute("""
                      INSERT INTO positions(user_id, symbol, qty)
                      VALUES (%s,%s,%s)
                      ON CONFLICT (user_id, symbol)
                      DO UPDATE SET qty = positions.qty + EXCLUDED.qty
                    """, (u["id"], symbol, trade_qty))
                    cur.execute("""
                      INSERT INTO positions(user_id, symbol, qty)
                      VALUES (%s,%s,%s)
                      ON CONFLICT (user_id, symbol)
                      DO UPDATE SET qty = positions.qty + EXCLUDED.qty
                    """, (r["user_id"], symbol, -trade_qty))

                    if trade_qty == r_qty:
                        cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (r["id"],))
                    else:
                        cur.execute("UPDATE orders SET qty = qty - %s WHERE id=%s", (trade_qty, r["id"]))

                    remain -= trade_qty

                if remain == 0:
                    cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (order_id,))

            else:  # SELL
                # проверяем позицию продавца
                cur.execute("SELECT qty FROM positions WHERE user_id=%s AND symbol=%s FOR UPDATE", (u["id"], symbol))
                p = cur.fetchone()
                pos = D(p["qty"]) if p else D("0")
                if pos < qty:
                    # нет бумаг — оставим NEW
                    return

                # встречные BUY с ценой >= нашей
                cur.execute("""
                  SELECT id,user_id,price,qty FROM orders
                  WHERE symbol=%s AND side='BUY' AND status='NEW' AND price>=%s
                  ORDER BY price DESC, created_at ASC
                  FOR UPDATE SKIP LOCKED
                """, (symbol, price))
                rows = cur.fetchall()
                remain = qty
                for r in rows:
                    if remain <= 0: break
                    r_qty = D(r["qty"])
                    r_px  = D(r["price"])
                    trade_qty = remain if remain <= r_qty else r_qty
                    amount = trade_qty * r_px

                    # списать бумаги у продавца
                    cur.execute("UPDATE positions SET qty = qty - %s WHERE user_id=%s AND symbol=%s", (trade_qty, u["id"], symbol))
                    # начислить деньги продавцу
                    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, u["id"]))
                    # покупателю — бумаги
                    cur.execute("""
                      INSERT INTO positions(user_id, symbol, qty)
                      VALUES (%s,%s,%s)
                      ON CONFLICT (user_id, symbol)
                      DO UPDATE SET qty = positions.qty + EXCLUDED.qty
                    """, (r["user_id"], symbol, trade_qty))

                    if trade_qty == r_qty:
                        cur.execute("UPDATE orders SET status='FILLED' WHERE id=%s", (r["id"],))
                    else:
                        cur.execute("UPDATE orders SET qty = qty - %s WHERE id=%s", (trade_qty, r["id"]))

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
