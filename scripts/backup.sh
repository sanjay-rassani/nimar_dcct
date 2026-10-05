#!/bin/sh
# Daily Postgres + evidence backup loop for docker-compose.prod.yml
set -eu

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_DIR="/backups"
MEDIA_SRC="/app/media"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"

mkdir -p "$BACKUP_DIR/db" "$BACKUP_DIR/media"

echo "Backup sidecar started. Retention=${RETENTION_DAYS}d interval=${INTERVAL_SECONDS}s"

while true; do
  STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
  DB_FILE="$BACKUP_DIR/db/nimar_dcct_${STAMP}.sql.gz"
  MEDIA_FILE="$BACKUP_DIR/media/media_${STAMP}.tar.gz"

  echo "[$STAMP] Backing up database to $DB_FILE"
  if pg_dump | gzip > "$DB_FILE"; then
    echo "[$STAMP] DB backup OK"
  else
    echo "[$STAMP] DB backup FAILED" >&2
  fi

  echo "[$STAMP] Backing up media/evidence to $MEDIA_FILE"
  if tar -czf "$MEDIA_FILE" -C "$MEDIA_SRC" . 2>/dev/null; then
    echo "[$STAMP] Media backup OK"
  else
    echo "[$STAMP] Media backup skipped/failed (empty or unavailable)" >&2
  fi

  # Retention prune
  find "$BACKUP_DIR/db" -type f -name '*.sql.gz' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
  find "$BACKUP_DIR/media" -type f -name '*.tar.gz' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

  sleep "$INTERVAL_SECONDS"
done
