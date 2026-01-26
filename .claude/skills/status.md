---
name: status
description: Quick health check of all Clawd services (containers, DB, Redis)
triggers:
  - "status"
  - "health check"
  - "서비스 상태"
  - "컨테이너 확인"
---

## Instructions

Run these commands to check system health:

```bash
# Container status
docker compose ps

# PostgreSQL health
docker compose exec -T postgres pg_isready

# Redis health
docker compose exec -T redis redis-cli ping

# Recent health data (last 3 days)
docker compose exec -T postgres psql -U clawd_user -d clawd_db -c "SELECT date, sleep_hours, resting_hr, stress_level FROM health_daily ORDER BY date DESC LIMIT 3;"
```

Report results concisely. No exploration needed.
