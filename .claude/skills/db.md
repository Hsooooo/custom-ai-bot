---
name: db
description: Common database queries for health and exercise data
triggers:
  - "db"
  - "database"
  - "데이터베이스"
  - "쿼리"
  - "건강 데이터"
  - "운동 데이터"
---

## Instructions

Database: PostgreSQL, User: clawd_user, DB: clawd_db

### Tables
- `health_daily`: date, sleep_hours, sleep_score, resting_hr, hrv_status, stress_level, body_battery_max, body_battery_min
- `exercise_activity`: activity_id, activity_type, activity_name, start_time, duration_sec, distance_meters, avg_hr, avg_pace

### Common Queries

```bash
# Recent health data
docker compose exec -T postgres psql -U clawd_user -d clawd_db -c "SELECT * FROM health_daily ORDER BY date DESC LIMIT 7;"

# Recent exercises
docker compose exec -T postgres psql -U clawd_user -d clawd_db -c "SELECT activity_type, activity_name, start_time, distance_meters, avg_pace FROM exercise_activity ORDER BY start_time DESC LIMIT 10;"

# Health stats (last 30 days)
docker compose exec -T postgres psql -U clawd_user -d clawd_db -c "SELECT AVG(sleep_hours)::numeric(4,2) as avg_sleep, AVG(resting_hr)::int as avg_hr, AVG(stress_level)::int as avg_stress FROM health_daily WHERE date > CURRENT_DATE - 30;"

# Custom query
docker compose exec -T postgres psql -U clawd_user -d clawd_db -c "{query}"
```
