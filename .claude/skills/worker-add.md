---
name: worker-add
description: Add a new worker to Clawd system
triggers:
  - "add worker"
  - "new worker"
  - "워커 추가"
  - "새 워커"
---

## Instructions

### 1. Create worker directory
```bash
mkdir -p workers/worker-{name}
```

### 2. Create main.py
Template structure:
```python
import os
import schedule
import time
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'postgres'),
        database=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD')
    )

def main_task():
    # Worker logic here
    pass

if __name__ == "__main__":
    schedule.every(1).hours.do(main_task)
    main_task()  # Run immediately on start
    while True:
        schedule.run_pending()
        time.sleep(60)
```

### 3. Create requirements.txt
```
psycopg2-binary>=2.9.0
schedule>=1.2.0
```

### 4. Create Dockerfile
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-u", "main.py"]
```

### 5. Add to docker-compose.yml
```yaml
worker-{name}:
  build: ./workers/worker-{name}
  restart: unless-stopped
  depends_on:
    - postgres
  environment:
    - TZ=${TZ}
    - POSTGRES_HOST=postgres
    - POSTGRES_DB=${POSTGRES_DB}
    - POSTGRES_USER=${POSTGRES_USER}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  networks:
    - clawd_net
```

### 6. Deploy
```bash
docker compose up -d --build worker-{name}
```
