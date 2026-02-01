#!/usr/bin/env bash
set -euo pipefail

# custom-ai-bot backup script
# - Postgres dump (custom-ai-bot-postgres-1)
# - File snapshots (obsidian_vault + OpenClaw state)
# - Local retention rotation

TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
BASE_DIR="${BACKUP_DIR:-/home/ubuntu/backups/custom-ai-bot}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

# Containers / paths
PG_CONTAINER="${PG_CONTAINER:-custom-ai-bot-postgres-1}"
PG_USER="${POSTGRES_USER:-clawd_user}"
PG_DB="${POSTGRES_DB:-clawd_db}"

OBSIDIAN_DIR="${OBSIDIAN_DIR:-/home/ubuntu/custom-ai-bot/obsidian_vault}"
OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-/home/ubuntu/.openclaw}"
MEDIA_DIR="${MEDIA_DIR:-/home/ubuntu/.openclaw/media}"

mkdir -p "$BASE_DIR"

# 1) Postgres dump
PG_OUT="$BASE_DIR/postgres_${PG_DB}_${TS_UTC}.sql.gz"
echo "[backup] postgres -> $PG_OUT"
# pg_dump inside container avoids host dependency
# Use gzip on host for smaller size.
docker exec -i "$PG_CONTAINER" pg_dump -U "$PG_USER" "$PG_DB" | gzip -c > "$PG_OUT"

# 2) File snapshots
FILES_OUT="$BASE_DIR/files_${TS_UTC}.tar.gz"
echo "[backup] files -> $FILES_OUT"
# Archive only if paths exist
TMP_LIST="$(mktemp)"
trap 'rm -f "$TMP_LIST"' EXIT

if [ -d "$OBSIDIAN_DIR" ]; then echo "$OBSIDIAN_DIR" >> "$TMP_LIST"; fi
if [ -d "$OPENCLAW_STATE_DIR" ]; then echo "$OPENCLAW_STATE_DIR" >> "$TMP_LIST"; fi
if [ -d "$MEDIA_DIR" ]; then echo "$MEDIA_DIR" >> "$TMP_LIST"; fi

if [ -s "$TMP_LIST" ]; then
  tar -czf "$FILES_OUT" -T "$TMP_LIST"
else
  echo "[backup] no file paths found; skipping files archive"
fi

# 3) Retention cleanup
# Delete backups older than RETENTION_DAYS
# (safe: only within BASE_DIR)
echo "[backup] rotate >${RETENTION_DAYS}d in $BASE_DIR"
find "$BASE_DIR" -maxdepth 1 -type f \( -name 'postgres_*.sql.gz' -o -name 'files_*.tar.gz' \) -mtime "+$RETENTION_DAYS" -print -delete || true

echo "[backup] done"
