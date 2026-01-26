# Clawd Bot Replica - VPS Automation

This project replicates the "Clawd.bot" automation structure using Docker Compose.

## Structure

- **clawd**: Central bot gateway (stub)
- **workers/worker-garmin**: Fetches Garmin data, saves to DB, generates Obsidian notes.
- **workers/worker-brief**: Morning briefing (stub)
- **workers/worker-notes**: Obsidian note manager (stub)
- **workers/worker-monitor**: VPS health monitor (stub)
- **postgres**: Database for health and logs
- **obsidian_vault**: Git-synced vault structure

## Setup

1. **Clone & Configure**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Run (VPS)**
   ```bash
   docker compose up -d --build
   ```

3. **Check Logs**
   ```bash
   docker compose logs -f worker-garmin
   ```

4. **Verify Obsidian**
   Check `obsidian_vault/Health/` for generated markdown files.

## Development

- To add logic to other workers, edit the `main.py` in their respective directories.
- To change schedule, edit the `schedule.every()...` lines in `main.py`.
