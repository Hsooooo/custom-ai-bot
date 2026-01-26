# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Clawd Bot is a personal health & productivity automation system running on VPS via Docker Compose. It syncs Garmin health data, sends Telegram briefings, and auto-generates Obsidian notes.

**Current State**: Phase 1-2 complete (data foundation). Phase 3 (AI agent architecture) is planned but not yet implemented.

## Build & Run Commands

```bash
# Start all services
docker compose up -d --build

# View logs (all services)
docker compose logs -f

# View specific worker logs
docker compose logs -f worker-garmin
docker compose logs -f worker-brief

# Check running containers
docker compose ps

# Restart specific service
docker compose restart worker-garmin
```

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov
```

## Database Access

```bash
# Connect to PostgreSQL
docker exec -it custom-ai-bot-postgres-1 psql -U clawd_user -d clawd_db

# Check health data
docker exec -it custom-ai-bot-postgres-1 psql -U clawd_user -d clawd_db -c "SELECT * FROM health_daily ORDER BY date DESC LIMIT 5;"

# Clear Redis cache
docker exec -it custom-ai-bot-redis-1 redis-cli FLUSHALL
```

## Architecture

```
Docker Network
├── clawd (Telegram bot) ─> Commands: /start, /status, /brief
├── postgres (PostgreSQL 15)
├── redis (caching, rate limiting)
└── Workers:
    ├── worker-garmin   - Syncs Garmin data every 4 hours
    ├── worker-brief    - Sends briefings at 07:00 and 22:00
    ├── worker-notes    - Generates Obsidian notes (daily at 00:05, weekly Sunday 21:00)
    └── worker-monitor  - Health checks every 5 minutes
```

**Data Flow**: Garmin API → PostgreSQL + Obsidian markdown files → Telegram notifications

## Key Directories

- `clawd/` - Telegram bot gateway (python-telegram-bot)
- `workers/worker-*/` - Individual worker services, each with main.py, requirements.txt, Dockerfile
- `workers/shared/` - Shared utilities (redis_utils.py for caching, rate limiting, job queue)
- `obsidian_vault/` - Auto-generated markdown files (Health/, Exercise/, Daily/, Weekly/)
- `tests/` - pytest test suite with fixtures in conftest.py

## Database Schema

**health_daily**: date (PK), sleep_hours, sleep_score, resting_hr, hrv_status, stress_level, body_battery_max/min, raw_data (JSONB)

**exercise_activity**: activity_id (PK), activity_type, activity_name, start_time, duration_sec, distance_meters, avg_hr, max_hr, avg_pace, calories, elevation_gain, raw_data (JSONB)

## Adding a New Worker

1. Create `workers/worker-<name>/` with main.py, requirements.txt, Dockerfile
2. Add service to docker-compose.yml
3. Rebuild: `docker compose up -d --build`

## Tech Stack

- Python 3.10
- PostgreSQL 15, Redis (Alpine)
- python-telegram-bot 20.7
- garminconnect >= 0.2.38
- httpx (async HTTP), schedule (cron-like scheduling)
- pytest with pytest-asyncio

## Local Skills (Token-Saving)

Pre-configured skills in `.claude/skills/` for common tasks. Use these instead of exploring:

| Skill | Trigger Keywords | Purpose |
|-------|------------------|---------|
| `status` | "status", "health check" | Check all services, DB, Redis |
| `logs` | "logs", "에러 확인" | View worker logs |
| `deploy` | "deploy", "배포", "restart" | Build and restart services |
| `db` | "db", "쿼리", "건강 데이터" | Database queries |
| `test` | "test", "pytest" | Run tests |
| `worker-add` | "add worker", "워커 추가" | Template for new workers |
| `troubleshoot` | "troubleshoot", "문제", "fix" | Common issue fixes |
| `context` | "context", "프로젝트 설명" | Quick project overview |

## Troubleshooting

**Garmin login issues**: Clear cached session with `docker compose exec worker-garmin rm -rf /app/.garth && docker compose restart worker-garmin`

**Database connection**: Check with `docker compose exec postgres pg_isready`

**Redis issues**: Test with `docker compose exec redis redis-cli ping`
