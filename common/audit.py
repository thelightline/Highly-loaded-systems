import uuid, json
from datetime import datetime, timezone

def append_outbox(conn, *, event_type, entity_type, entity_id, payload,
                  event_id=None, ts=None, actor=None, correlation_id=None, causation_id=None):
    if event_id is None:
        import uuid as _u; event_id = _u.uuid4()
    if ts is None:
        ts = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("""
          INSERT INTO outbox.events(event_id, ts, entity_type, entity_id, event_type, payload, actor, correlation_id, causation_id)
          VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
          ON CONFLICT (event_id) DO NOTHING
        """, (str(event_id), ts, entity_type, entity_id, event_type, json.dumps(payload),
              actor, str(correlation_id) if correlation_id else None, str(causation_id) if causation_id else None))
    return event_id
