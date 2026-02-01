# Backups (custom-ai-bot)

This repo includes a simple local backup script:
- Postgres dump (`pg_dump` from the `custom-ai-bot-postgres-1` container)
- File archives:
  - `obsidian_vault`
  - OpenClaw state (`~/.openclaw`)
  - OpenClaw media (`~/.openclaw/media`)
- Local retention cleanup (default: 14 days)

## Run once

```bash
/home/ubuntu/custom-ai-bot/tools/backup/backup.sh
```

Outputs (default):
- `/home/ubuntu/backups/custom-ai-bot/postgres_<db>_<timestamp>.sql.gz`
- `/home/ubuntu/backups/custom-ai-bot/files_<timestamp>.tar.gz`

## Schedule (cron)
Recommended cron entry (KST):

```cron
CRON_TZ=Asia/Seoul
15 3 * * * /home/ubuntu/custom-ai-bot/tools/backup/backup.sh >> /home/ubuntu/backups/custom-ai-bot/backup.log 2>&1
```

## Config
Override via env vars (cron can export them):
- `BACKUP_DIR` (default `/home/ubuntu/backups/custom-ai-bot`)
- `BACKUP_RETENTION_DAYS` (default `14`)
- `PG_CONTAINER` (default `custom-ai-bot-postgres-1`)
- `POSTGRES_USER` (default `clawd_user`)
- `POSTGRES_DB` (default `clawd_db`)
- `OBSIDIAN_DIR` (default `/home/ubuntu/custom-ai-bot/obsidian_vault`)
- `OPENCLAW_STATE_DIR` (default `/home/ubuntu/.openclaw`)
- `MEDIA_DIR` (default `/home/ubuntu/.openclaw/media`)

## Next step (recommended)
Local-only backups are better than nothing, but the best practice is to add offsite storage
(e.g. Cloudflare R2 / Backblaze B2 / Wasabi / S3).
Use `rclone` or vendor CLI to sync `/home/ubuntu/backups/custom-ai-bot/` to offsite.
