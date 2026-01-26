---
name: system-monitor
description: Monitor server and Docker container status
triggers:
  - "server"
  - "status"
  - "시스템"
  - "서버"
  - "docker"
  - "container"
  - "컨테이너"
  - "디스크"
  - "메모리"
  - "cpu"
---

## Instructions

Monitor the VPS server and Docker containers.

### System Status

```bash
# CPU and Memory usage
top -bn1 | head -15

# Disk usage
df -h

# Memory details
free -h

# Uptime
uptime
```

### Docker Status

```bash
# List running containers
docker ps

# Container resource usage
docker stats --no-stream

# Check specific container logs
docker logs --tail 50 custom-ai-bot-clawd-1
docker logs --tail 50 custom-ai-bot-worker-garmin-1
docker logs --tail 50 custom-ai-bot-worker-brief-1

# Container health
docker inspect --format='{{.State.Health.Status}}' custom-ai-bot-postgres-1
```

### Database Status

```bash
# Check PostgreSQL is running
docker exec custom-ai-bot-postgres-1 pg_isready

# Database size
docker exec custom-ai-bot-postgres-1 psql -U clawd_user -d clawd_db -c "SELECT pg_size_pretty(pg_database_size('clawd_db'));"
```

### Redis Status

```bash
# Check Redis
docker exec custom-ai-bot-redis-1 redis-cli ping

# Redis memory usage
docker exec custom-ai-bot-redis-1 redis-cli info memory | grep used_memory_human
```

### Response Guidelines

- Report status in Korean
- Highlight any issues (high CPU, low disk, container errors)
- Suggest actions if problems detected
