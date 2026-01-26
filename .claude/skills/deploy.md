---
name: deploy
description: Build and deploy Clawd services
triggers:
  - "deploy"
  - "배포"
  - "빌드"
  - "재시작"
  - "restart"
---

## Instructions

```bash
# Full rebuild and restart
docker compose up -d --build

# Restart specific worker only (faster)
docker compose restart {worker_name}

# Rebuild specific worker
docker compose up -d --build {worker_name}
```

After deploy, run `docker compose ps` to verify all services are running.
