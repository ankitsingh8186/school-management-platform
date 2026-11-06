#!/usr/bin/env bash
# Logical backup (pg_dump custom format) into ./backups/
source "$(dirname "$0")/_env.sh"
mkdir -p backups
OUT="backups/school_$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$OUT"
[ -s "$OUT" ] || { rm -f "$OUT"; echo "Backup failed (empty file)" >&2; exit 1; }
echo "Backup written: $OUT ($(wc -c < "$OUT") bytes)"
