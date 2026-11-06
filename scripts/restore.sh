#!/usr/bin/env bash
# Restore a backup:  scripts/restore.sh backups/school_XXXX.dump
source "$(dirname "$0")/_env.sh"
FILE="${1:?usage: scripts/restore.sh <backup.dump>}"
[ -s "$FILE" ] || { echo "Backup file not found or empty: $FILE" >&2; exit 1; }
echo "Stopping app so nothing writes during restore..."
docker compose stop app
docker compose exec -T db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$FILE"
docker compose start app
wait_ready 90
echo "Restore complete. Row counts:"
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT (SELECT COUNT(*) FROM attendance) AS attendance, (SELECT COUNT(*) FROM audit_log) AS audit_log;"'
