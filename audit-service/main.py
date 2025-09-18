from fastapi import FastAPI, Query
from typing import Optional, List
import psycopg, json, os
from datetime import datetime

app = FastAPI()
DSN = os.getenv("DB_DSN", "postgresql://app_audit:app_audit@db-audit:5432/audit")

@app.get("/events")
def list_events(event_type: Optional[str]=None,
                entity_type: Optional[str]=None,
                entity_id: Optional[str]=None,
                since: Optional[str]=None,
                until: Optional[str]=None,
                limit: int=200):
    where, params = [], []
    if event_type:  where += ["event_type=%s"];     params += [event_type]
    if entity_type: where += ["entity_type=%s"];    params += [entity_type]
    if entity_id:   where += ["entity_id=%s"];      params += [entity_id]
    if since:       where += ["ts >= %s"];          params += [since]
    if until:       where += ["ts < %s"];           params += [until]
    sql = "SELECT ts,event_id,event_type,entity_type,entity_id,payload FROM audit.events"
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC, seq DESC LIMIT %s"
    params += [limit]
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {"ts": r[0].isoformat(), "event_id": str(r[1]), "event_type": r[2],
         "entity_type": r[3], "entity_id": r[4], "payload": r[5]}
        for r in rows
    ]
