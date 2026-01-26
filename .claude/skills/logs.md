---
name: logs
description: View worker logs efficiently
triggers:
  - "logs"
  - "로그"
  - "로그 확인"
  - "에러 확인"
---

## Instructions

Worker names: `clawd`, `worker-garmin`, `worker-brief`, `worker-notes`, `worker-monitor`

```bash
# Specific worker (default: last 50 lines)
docker compose logs --tail=50 {worker_name}

# All workers with errors
docker compose logs --tail=100 2>&1 | grep -i error

# Follow logs in real-time
docker compose logs -f {worker_name}
```

If user doesn't specify worker, ask which one or show all errors.
