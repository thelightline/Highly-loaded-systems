#!/usr/bin/env bash
set -euo pipefail

ts="$(date +'%Y%m%d-%H%M%S')"
file="${BACKUP_DIR}/${PGDATABASE}-${ts}.dump"

echo "[backup] $(date -Is) start pg_dump -> ${file}"
pg_dump -Fc -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$file"
echo "[backup] $(date -Is) done"

echo "[backup] rotate to $RETAIN files"
ls -1t "${BACKUP_DIR}/${PGDATABASE}-"*.dump 2>/dev/null | tail -n +$((RETAIN+1)) | xargs -r rm -f
