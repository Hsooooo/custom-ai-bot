---
name: context
description: Quick project context without exploration (saves tokens)
triggers:
  - "context"
  - "프로젝트 설명"
  - "이 프로젝트"
---

## Clawd Bot Project Context

**Type**: Personal health automation system (Docker Compose microservices)

**Current State**: Phase 1-2 complete (data foundation). Phase 3 (AI agent) planned.

**Services**:
- `clawd` - Telegram bot (/start, /status, /brief)
- `worker-garmin` - Garmin sync every 4h (sleep, HR, HRV, stress, activities)
- `worker-brief` - Daily briefings at 07:00, 22:00 (weather, calendar, GitHub)
- `worker-notes` - Obsidian notes (daily 00:05, weekly Sunday 21:00)
- `worker-monitor` - System health checks every 5min

**Database**: PostgreSQL (health_daily, exercise_activity tables)

**Cache**: Redis (weather 30min, GitHub 15min, calendar 5min TTL)

**Key Paths**:
- `clawd/main.py` - Bot commands
- `workers/worker-*/main.py` - Worker logic
- `workers/shared/redis_utils.py` - Caching, rate limiting
- `obsidian_vault/` - Auto-generated markdown

**Tech**: Python 3.10, python-telegram-bot 20.7, garminconnect, httpx, schedule

**Roadmap**: See ROADMAP.md for Phase 3+ AI agent plans (Milestones 9-15)

NO EXPLORATION NEEDED - use this context directly.
