---
name: health-stats
description: Get health and sleep stats from Garmin/Postgres database
triggers:
  - "sleep"
  - "stress"
  - "heart rate"
  - "briefing"
  - "health"
  - "수면"
  - "심박"
  - "스트레스"
  - "건강"
  - "컨디션"
  - "body battery"
  - "hrv"
---

## Instructions

When the user asks about health data:

1. **Identify the query type**:
   - Sleep data → `python /app/workers/worker-brief/query.py health --days 3`
   - Exercise data → `python /app/workers/worker-brief/query.py exercise --days 7`
   - Full briefing → `python /app/workers/worker-brief/query.py briefing`

2. **For specific dates**:
   - "어제" → `--date $(date -d "yesterday" +%Y-%m-%d)`
   - "이번주" → `--days 7`
   - "지난달" → `--days 30`

3. **Run the command and summarize**:
   - Parse the JSON output
   - Provide insights in natural Korean
   - Compare to averages if multiple days of data

## Example Commands

```bash
# Get today's health data
python /app/workers/worker-brief/query.py health

# Get last 7 days
python /app/workers/worker-brief/query.py health --days 7

# Get exercise history
python /app/workers/worker-brief/query.py exercise --days 7 --limit 5

# Full text briefing
python /app/workers/worker-brief/query.py briefing
```

## Response Guidelines

- Use Korean for responses
- Include specific numbers (e.g., "7시간 수면", "심박수 62bpm")
- Provide context (e.g., "평소보다 수면이 부족해요")
- Add friendly advice based on data
