# audit-forwarder/main.py
import os, json, time
import psycopg
BATCH = 200
TRADING_DSN = os.getenv("TRADING_DSN", "postgresql://app:app@db-primary:5432/trading")
AUDIT_DSN   = os.getenv("AUDIT_DSN",   "postgresql://app_audit:app_audit@db-audit:5432/audit")

def once():
    shipped = 0
    with psycopg.connect(TRADING_DSN) as src, psycopg.connect(AUDIT_DSN) as dst:
        with src.transaction():
            rows = src.execute("""
              SELECT id, event_id, ts, entity_type, entity_id, event_type, payload, actor, correlation_id, causation_id
              FROM outbox.events
              WHERE published_at IS NULL
              ORDER BY ts, id
              FOR UPDATE SKIP LOCKED
              LIMIT %s
            """, (BATCH,)).fetchall()
            if not rows:
                return 0
            with dst.transaction():
                for r in rows:
                    (_id, ev_id, ts, ent_t, ent_id, ev_t, payload, actor, corr, caus) = r
                    dst.execute("INSERT INTO audit.event_ids(event_id, ts) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                                (str(ev_id), ts))
                    dst.execute("""
                      INSERT INTO audit.events (ts, event_id, entity_type, entity_id, event_type, payload, actor, correlation_id, causation_id)
                      VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                    """, (ts, str(ev_id), ent_t, ent_id, ev_t, json.dumps(payload), actor, corr, caus))
                src.execute("""
                  UPDATE outbox.events
                  SET published_at = now(), attempts = attempts + 1
                  WHERE id = ANY(%s)
                """, ([r[0] for r in rows],))
                shipped = len(rows)
    return shipped

if __name__ == "__main__":
    backoff = 1.0
    while True:
        try:
            n = once()
            backoff = 1.0
            time.sleep(0.5 if n else 2.0)
        except psycopg.OperationalError as e:
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
        except Exception as e:
            print("forwarder error:", repr(e))
            time.sleep(1.0)
