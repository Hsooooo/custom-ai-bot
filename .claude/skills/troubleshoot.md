---
name: troubleshoot
description: Quick troubleshooting for common Clawd issues
triggers:
  - "troubleshoot"
  - "문제"
  - "에러"
  - "안됨"
  - "fix"
---

## Instructions

### Garmin Login Issues
```bash
docker compose logs worker-garmin | grep -i error
docker compose exec worker-garmin rm -rf /app/.garth
docker compose restart worker-garmin
```

### Database Connection
```bash
docker compose exec -T postgres pg_isready
docker compose restart postgres
```

### Redis Issues
```bash
docker compose exec -T redis redis-cli ping
docker compose exec -T redis redis-cli FLUSHALL  # Clear cache
docker compose restart redis
```

### Container Not Starting
```bash
docker compose logs {service_name}
docker compose up -d --build {service_name}
```

### Full Reset
```bash
docker compose down
docker compose up -d --build
```

### Check Resource Usage
```bash
docker stats --no-stream
```
