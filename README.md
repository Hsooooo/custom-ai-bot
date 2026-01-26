# Clawd Bot - Personal Health & Productivity Automation

VPS에서 실행되는 개인 건강 자동화 시스템입니다. Garmin 웨어러블 데이터를 수집하고, 텔레그램을 통해 건강 브리핑을 제공하며, Obsidian 노트를 자동 생성합니다.

> Inspired by [Clawd.bot](https://clawd.bot)

## Features

### Health Data Sync (Garmin Connect)
- 수면 시간, 수면 점수
- 안정시 심박수, HRV 상태
- 스트레스 레벨, Body Battery
- 운동 활동 (러닝, 사이클, 수영 등)

### Daily Briefings (Telegram)
- 매일 07:00 아침 브리핑
- 매일 22:00 저녁 요약
- 날씨, 일정, GitHub 활동 포함

### Obsidian Integration
- 일별 건강 마크다운 자동 생성
- 운동 로그 마크다운 생성
- 데일리/위클리 노트 자동화

### System Monitoring
- Docker 컨테이너 상태 모니터링
- 디스크/메모리 사용량 체크
- 이상 감지 시 텔레그램 알림

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │  clawd   │    │   postgres   │    │    redis     │           │
│  │  (bot)   │───▶│   (data)     │◀───│   (cache)    │           │
│  └──────────┘    └──────────────┘    └──────────────┘           │
│        │                 ▲                   ▲                   │
│        │                 │                   │                   │
│  ┌─────┴─────────────────┴───────────────────┴─────┐            │
│  │                    Workers                       │            │
│  ├─────────────┬─────────────┬───────────┬─────────┤            │
│  │   garmin    │    brief    │   notes   │ monitor │            │
│  │  (health)   │ (briefing)  │(obsidian) │ (system)│            │
│  └─────────────┴─────────────┴───────────┴─────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       External Services        │
              ├───────────────────────────────┤
              │  Garmin Connect  │  Telegram  │
              │  OpenWeatherMap  │  Calendar  │
              │  GitHub API      │  Obsidian  │
              └───────────────────────────────┘
```

---

## Project Structure

```
custom-ai-bot/
├── clawd/                      # Telegram Bot Gateway
│   ├── main.py                 # Bot commands (/status, /brief)
│   ├── requirements.txt
│   └── Dockerfile
│
├── workers/
│   ├── worker-garmin/          # Garmin Data Sync
│   │   ├── main.py             # Health + Activity sync
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── worker-brief/           # Daily Briefing
│   │   ├── main.py             # Morning/Evening briefings
│   │   ├── external_services.py # Weather, Calendar, GitHub
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── worker-notes/           # Obsidian Automation
│   │   ├── main.py             # Daily/Weekly note generation
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── worker-monitor/         # System Monitoring
│   │   ├── main.py             # Container & resource monitoring
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── shared/                 # Shared Modules
│       └── redis_utils.py      # Caching, Rate Limiting
│
├── obsidian_vault/             # Obsidian Vault (Git-synced)
│   ├── Health/                 # Auto-generated health notes
│   ├── Exercise/               # Auto-generated exercise logs
│   ├── Daily/                  # Daily notes
│   ├── Weekly/                 # Weekly reviews
│   └── templates/
│       ├── Daily_Template.md
│       └── Weekly_Template.md
│
├── tests/                      # Test Suite
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_garmin_parser.py
│   └── test_markdown_generator.py
│
├── docker-compose.yml
├── .env.example
├── ROADMAP.md
└── README.md
```

---

## Quick Start

### 1. Clone & Configure

```bash
git clone <repository-url>
cd custom-ai-bot

cp .env.example .env
# Edit .env with your credentials
```

### 2. Required Environment Variables

```bash
# Core (Required)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_ID=your_telegram_user_id
GARMIN_EMAIL=your_garmin_email
GARMIN_PASSWORD=your_garmin_password
POSTGRES_USER=clawd_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=clawd_db

# Optional - External Services
OPENWEATHER_API_KEY=your_openweather_key    # Weather in briefings
GOOGLE_CALENDAR_API_KEY=your_calendar_key   # Calendar in briefings
GITHUB_TOKEN=your_github_token              # GitHub activity
GITHUB_USERNAME=your_github_username
```

### 3. Run

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Check specific worker
docker compose logs -f worker-garmin
docker compose logs -f worker-brief
```

### 4. Verify

```bash
# Check running containers
docker compose ps

# Check health data
docker exec -it custom-ai-bot-postgres-1 psql -U clawd_user -d clawd_db -c "SELECT * FROM health_daily ORDER BY date DESC LIMIT 5;"

# Check Obsidian files
ls -la obsidian_vault/Health/
ls -la obsidian_vault/Exercise/
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Bot introduction and command list |
| `/status` | Server status (CPU, Memory, Disk, Uptime) |
| `/brief` | Manual health briefing |

---

## Schedules

| Worker | Schedule | Description |
|--------|----------|-------------|
| worker-garmin | Every 4 hours | Sync health & activity data |
| worker-brief | 07:00, 22:00 | Send daily briefings |
| worker-notes | 00:05 daily, 21:00 Sunday | Generate daily/weekly notes |
| worker-monitor | Every 5 minutes, 09:00 daily | Health check & daily report |

---

## Database Schema

### health_daily
```sql
CREATE TABLE health_daily (
    date DATE PRIMARY KEY,
    sleep_hours NUMERIC,
    sleep_score INTEGER,
    resting_hr INTEGER,
    hrv_status TEXT,
    stress_level INTEGER,
    body_battery_max INTEGER,
    body_battery_min INTEGER,
    raw_data JSONB,
    updated_at TIMESTAMP
);
```

### exercise_activity
```sql
CREATE TABLE exercise_activity (
    activity_id BIGINT PRIMARY KEY,
    activity_type TEXT,
    activity_name TEXT,
    start_time TIMESTAMP,
    duration_sec INTEGER,
    distance_meters NUMERIC,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_pace TEXT,
    calories INTEGER,
    elevation_gain NUMERIC,
    raw_data JSONB,
    created_at TIMESTAMP
);
```

---

## Redis Usage

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `cache:weather` | 30 min | Weather API response cache |
| `cache:github` | 15 min | GitHub activity cache |
| `cache:calendar` | 5 min | Calendar events cache |
| `ratelimit:*` | - | API rate limiting (Token Bucket) |

---

## Briefing Example

```
🌅 Good Morning!

🌤 Seoul: 3°C (체감 -1°C)
   맑음, 습도 45%

📅 오늘 일정:
  • 10:00 Team Standup
  • 14:00 1:1 Meeting

😴 어제 수면: 7.5시간 (점수: 85)
🔋 Body Battery: 92% → 충전 완료!
💓 안정시 심박수: 58 bpm (HRV: BALANCED)
😰 평균 스트레스: 32

🏃 최근 운동:
  🏃 01/25 Morning Run: 5.2km (5:30/km)
  🚴 01/24 Evening Ride: 20.0km

💻 GitHub (24h):
  Commits: 5 | PRs: 2 | Issues: 1

---
✨ 오늘 컨디션 좋아 보여요! 좋은 하루 되세요!
```

---

## Development

### Run Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

### Add New Worker

1. Create directory: `workers/worker-<name>/`
2. Add `main.py`, `requirements.txt`, `Dockerfile`
3. Update `docker-compose.yml`
4. Rebuild: `docker compose up -d --build`

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f worker-garmin

# Last 100 lines
docker compose logs --tail=100 worker-brief
```

---

## Troubleshooting

### Garmin Login Issues
```bash
# Check Garmin worker logs
docker compose logs worker-garmin | grep -i error

# Clear cached session
docker compose exec worker-garmin rm -rf /app/.garth
docker compose restart worker-garmin
```

### Database Connection
```bash
# Check PostgreSQL
docker compose exec postgres pg_isready

# Connect directly
docker compose exec postgres psql -U clawd_user -d clawd_db
```

### Redis Issues
```bash
# Check Redis
docker compose exec redis redis-cli ping

# Clear cache
docker compose exec redis redis-cli FLUSHALL
```

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for detailed development plans.

### Completed
- [x] Garmin health data sync
- [x] Exercise activity tracking
- [x] Daily briefings (Telegram)
- [x] External services (Weather, Calendar, GitHub)
- [x] Obsidian note automation
- [x] System monitoring
- [x] Redis caching & rate limiting
- [x] Error handling & retry logic
- [x] Basic test suite

### Planned (Phase 3)
- [ ] AI-based health insights
- [ ] Predictive notifications
- [ ] Voice interface
- [ ] Web dashboard

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.10 |
| Database | PostgreSQL 15 |
| Cache | Redis Alpine |
| Container | Docker Compose |
| Bot | python-telegram-bot 20.7 |
| Health API | garminconnect >= 0.2.38 |
| HTTP Client | httpx (async) |
| Scheduling | schedule |
| Testing | pytest |

---

## License

MIT License

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request
