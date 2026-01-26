"""
Worker Notes - Obsidian Daily/Weekly Note Automation

Features:
- Automatic daily note creation based on template
- Weekly review generation with health summaries
- Tag management
- Template variable substitution
"""

import os
import sys
import time
import logging
import datetime
import re
import schedule
import psycopg2
import pytz
from pathlib import Path
from typing import Optional, Dict, List

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('worker-notes')

# Environment Variables
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
TZ = os.getenv("TZ", "Asia/Seoul")
OBSIDIAN_PATH = os.getenv("OBSIDIAN_PATH", "/obsidian")

# Template paths
TEMPLATES_PATH = Path(OBSIDIAN_PATH) / "templates"
DAILY_TEMPLATE = TEMPLATES_PATH / "Daily_Template.md"
WEEKLY_TEMPLATE = TEMPLATES_PATH / "Weekly_Template.md"

# Output paths
DAILY_PATH = Path(OBSIDIAN_PATH) / "Daily"
WEEKLY_PATH = Path(OBSIDIAN_PATH) / "Weekly"


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def get_health_data(date: datetime.date) -> Optional[Dict]:
    """Get health data for specific date."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT sleep_hours, sleep_score, resting_hr, hrv_status,
                   stress_level, body_battery_max, body_battery_min
            FROM health_daily
            WHERE date = %s
        """, (date,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                'sleep_hours': row[0],
                'sleep_score': row[1],
                'resting_hr': row[2],
                'hrv_status': row[3],
                'stress_level': row[4],
                'body_battery_max': row[5],
                'body_battery_min': row[6]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting health data: {e}")
        return None


def get_weekly_health_summary(start_date: datetime.date, end_date: datetime.date) -> Dict:
    """Get health summary for a week."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                AVG(sleep_hours) as avg_sleep,
                AVG(sleep_score) as avg_sleep_score,
                AVG(resting_hr) as avg_rhr,
                AVG(stress_level) as avg_stress,
                AVG(body_battery_max) as avg_bb,
                COUNT(*) as days_with_data
            FROM health_daily
            WHERE date BETWEEN %s AND %s
        """, (start_date, end_date))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return {
            'avg_sleep': round(row[0] or 0, 1),
            'avg_sleep_score': round(row[1] or 0),
            'avg_rhr': round(row[2] or 0),
            'avg_stress': round(row[3] or 0),
            'avg_bb': round(row[4] or 0),
            'days_with_data': row[5] or 0
        }
        
    except Exception as e:
        logger.error(f"Error getting weekly summary: {e}")
        return {}


def get_weekly_activities(start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
    """Get activities for a week."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT activity_type, activity_name, start_time, duration_sec,
                   distance_meters, calories
            FROM exercise_activity
            WHERE start_time::date BETWEEN %s AND %s
            ORDER BY start_time
        """, (start_date, end_date))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        activities = []
        for row in rows:
            activities.append({
                'type': row[0],
                'name': row[1],
                'start_time': row[2],
                'duration_sec': row[3],
                'distance_meters': row[4],
                'calories': row[5]
            })
        return activities
        
    except Exception as e:
        logger.error(f"Error getting weekly activities: {e}")
        return []


def get_recent_activities(date: datetime.date, limit: int = 3) -> List[Dict]:
    """Get recent activities up to the given date."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT activity_type, activity_name, start_time, duration_sec,
                   distance_meters, avg_pace, calories
            FROM exercise_activity
            WHERE start_time::date <= %s
            ORDER BY start_time DESC
            LIMIT %s
        """, (date, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        activities = []
        for row in rows:
            activities.append({
                'type': row[0],
                'name': row[1],
                'start_time': row[2],
                'duration_sec': row[3],
                'distance_meters': row[4],
                'avg_pace': row[5],
                'calories': row[6]
            })
        return activities
        
    except Exception as e:
        logger.error(f"Error getting recent activities: {e}")
        return []


def substitute_template_variables(template: str, date: datetime.date) -> str:
    """
    Substitute template variables.
    
    Supported variables:
    - {{date:FORMAT}} - Date in specified format (e.g., {{date:YYYY-MM-DD}})
    - {{yesterday:FORMAT}} - Yesterday's date
    - {{week:WW}} - Week number
    """
    result = template
    
    # Date format mapping
    format_map = {
        'YYYY': '%Y',
        'YY': '%y',
        'MM': '%m',
        'DD': '%d',
        'WW': '%W',
        'ddd': '%a',
        'dddd': '%A',
    }
    
    # Replace {{date:FORMAT}} patterns
    date_patterns = re.findall(r'\{\{date:([^}]+)\}\}', result)
    for pattern in date_patterns:
        py_format = pattern
        for k, v in format_map.items():
            py_format = py_format.replace(k, v)
        replacement = date.strftime(py_format)
        result = result.replace(f'{{{{date:{pattern}}}}}', replacement)
    
    # Replace {{yesterday:FORMAT}} patterns
    yesterday = date - datetime.timedelta(days=1)
    yesterday_patterns = re.findall(r'\{\{yesterday:([^}]+)\}\}', result)
    for pattern in yesterday_patterns:
        py_format = pattern
        for k, v in format_map.items():
            py_format = py_format.replace(k, v)
        replacement = yesterday.strftime(py_format)
        result = result.replace(f'{{{{yesterday:{pattern}}}}}', replacement)
    
    return result


def format_health_for_note(health: Optional[Dict]) -> str:
    """Format health data for daily note."""
    if not health:
        return "- No health data available"
    
    lines = []
    
    if health.get('sleep_hours'):
        lines.append(f"- 😴 **Sleep**: {health['sleep_hours']}h (Score: {health.get('sleep_score', 'N/A')})")
    
    if health.get('body_battery_max'):
        bb = health['body_battery_max']
        emoji = "🔋" if bb >= 50 else "🪫"
        lines.append(f"- {emoji} **Body Battery**: {bb}%")
    
    if health.get('resting_hr'):
        lines.append(f"- 💓 **Resting HR**: {health['resting_hr']} bpm")
    
    if health.get('stress_level'):
        lines.append(f"- 😰 **Stress**: {health['stress_level']}")
    
    if health.get('hrv_status'):
        lines.append(f"- 📊 **HRV**: {health['hrv_status']}")
    
    return "\n".join(lines) if lines else "- No health data available"


def format_condition(health: Optional[Dict]) -> str:
    """Generate condition summary based on health data."""
    if not health:
        return "데이터 없음"
    
    bb = health.get('body_battery_max', 0)
    sleep = health.get('sleep_hours', 0)
    stress = health.get('stress_level', 100)
    
    if bb >= 80 and sleep >= 7 and stress <= 30:
        return "🟢 최상 - 컨디션 좋음!"
    elif bb >= 60 and sleep >= 6:
        return "🟡 양호 - 괜찮은 상태"
    elif bb < 40 or sleep < 5:
        return "🔴 주의 - 휴식 필요"
    else:
        return "🟠 보통"


def create_daily_note(date: datetime.date) -> bool:
    """Create daily note for the specified date."""
    try:
        # Ensure directory exists
        DAILY_PATH.mkdir(parents=True, exist_ok=True)
        
        # Check if note already exists
        note_filename = f"{date.strftime('%Y-%m-%d')}.md"
        note_path = DAILY_PATH / note_filename
        
        if note_path.exists():
            logger.info(f"Daily note already exists: {note_path}")
            return True
        
        # Read template
        if DAILY_TEMPLATE.exists():
            template = DAILY_TEMPLATE.read_text(encoding='utf-8')
        else:
            # Default template
            template = """# Daily Note - {{date:YYYY-MM-DD}}

## ☀️ Morning Briefing
**Condition**: <!-- CONDITION_PLACEHOLDER -->

## 🏥 Health
<!-- HEALTH_PLACEHOLDER -->

## 📆 Schedule
- [ ] 

## ✅ Tasks
- [ ] 

## 📝 Notes

## 🏃 Activities
<!-- ACTIVITIES_PLACEHOLDER -->

---
Tags: #daily #{{date:YYYY}}/{{date:MM}}
"""
        
        # Substitute date variables
        content = substitute_template_variables(template, date)
        
        # Get health data (use yesterday's for sleep data)
        yesterday = date - datetime.timedelta(days=1)
        health = get_health_data(yesterday)
        today_health = get_health_data(date)
        
        # Use today's body battery, yesterday's sleep
        combined_health = {}
        if health:
            combined_health['sleep_hours'] = health.get('sleep_hours')
            combined_health['sleep_score'] = health.get('sleep_score')
        if today_health:
            combined_health['body_battery_max'] = today_health.get('body_battery_max')
            combined_health['resting_hr'] = today_health.get('resting_hr')
            combined_health['stress_level'] = today_health.get('stress_level')
            combined_health['hrv_status'] = today_health.get('hrv_status')
        
        # Replace placeholders
        health_text = format_health_for_note(combined_health if combined_health else None)
        condition_text = format_condition(combined_health if combined_health else None)
        
        content = content.replace('<!-- HEALTH_PLACEHOLDER -->', health_text)
        content = content.replace('<!-- CONDITION_PLACEHOLDER -->', condition_text)
        
        # Add recent activities
        activities = get_recent_activities(date, limit=3)
        if activities:
            activity_lines = []
            for act in activities:
                act_date = act['start_time'].strftime("%m/%d") if act['start_time'] else ""
                distance_km = (act['distance_meters'] or 0) / 1000
                
                type_emoji = {
                    'running': '🏃',
                    'cycling': '🚴',
                    'swimming': '🏊',
                }.get(act['type'], '💪')
                
                activity_lines.append(f"- {type_emoji} {act_date} {act.get('name', act['type'])}: {distance_km:.1f}km")
            
            content = content.replace('<!-- ACTIVITIES_PLACEHOLDER -->', '\n'.join(activity_lines))
        else:
            content = content.replace('<!-- ACTIVITIES_PLACEHOLDER -->', '- No recent activities')
        
        # Remove weather placeholder if present (will be filled by brief)
        content = content.replace('<!-- WEATHER_PLACEHOLDER -->', '')
        content = content.replace('<!-- CALENDAR_PLACEHOLDER -->', '- Check calendar')
        
        # Write note
        note_path.write_text(content, encoding='utf-8')
        logger.info(f"Created daily note: {note_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating daily note: {e}")
        return False


def create_weekly_note(date: datetime.date) -> bool:
    """Create weekly review note."""
    try:
        # Get week number and year
        year, week_num, _ = date.isocalendar()
        
        # Ensure directory exists
        WEEKLY_PATH.mkdir(parents=True, exist_ok=True)
        
        # Check if note already exists
        note_filename = f"{year}-W{week_num:02d}.md"
        note_path = WEEKLY_PATH / note_filename
        
        if note_path.exists():
            logger.info(f"Weekly note already exists: {note_path}")
            return True
        
        # Calculate week start/end (Monday to Sunday)
        week_start = date - datetime.timedelta(days=date.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        
        # Read template
        if WEEKLY_TEMPLATE.exists():
            template = WEEKLY_TEMPLATE.read_text(encoding='utf-8')
        else:
            # Default template
            template = """# Weekly Review - {{date:YYYY}}-W{{date:WW}}

## 📅 Week Overview
- **Period**: WEEK_START ~ WEEK_END

## 📊 Health Summary
<!-- HEALTH_SUMMARY_PLACEHOLDER -->

## 🏃 Exercise Log
<!-- EXERCISE_SUMMARY_PLACEHOLDER -->

## 🎯 Goals Review
- [ ] 

## 💡 Insights & Learnings

## ⏭️ Next Week Plan
- [ ] 

---
Tags: #weekly #{{date:YYYY}}
"""
        
        # Substitute date variables
        content = substitute_template_variables(template, date)
        
        # Replace week dates
        content = content.replace('WEEK_START', week_start.strftime('%Y-%m-%d'))
        content = content.replace('WEEK_END', week_end.strftime('%Y-%m-%d'))
        
        # Get weekly health summary
        health_summary = get_weekly_health_summary(week_start, week_end)
        if health_summary and health_summary.get('days_with_data', 0) > 0:
            health_lines = [
                f"- 😴 **Average Sleep**: {health_summary['avg_sleep']}h (Score: {health_summary['avg_sleep_score']})",
                f"- 💓 **Average Resting HR**: {health_summary['avg_rhr']} bpm",
                f"- 😰 **Average Stress**: {health_summary['avg_stress']}",
                f"- 🔋 **Average Body Battery**: {health_summary['avg_bb']}%",
                f"- 📊 **Days with data**: {health_summary['days_with_data']}/7"
            ]
            content = content.replace('<!-- HEALTH_SUMMARY_PLACEHOLDER -->', '\n'.join(health_lines))
        else:
            content = content.replace('<!-- HEALTH_SUMMARY_PLACEHOLDER -->', '- No health data for this week')
        
        # Get weekly activities
        activities = get_weekly_activities(week_start, week_end)
        if activities:
            total_distance = sum((a['distance_meters'] or 0) for a in activities) / 1000
            total_duration = sum((a['duration_sec'] or 0) for a in activities) / 60
            total_calories = sum((a['calories'] or 0) for a in activities)
            
            exercise_lines = [
                f"- **Total Activities**: {len(activities)}",
                f"- **Total Distance**: {total_distance:.1f} km",
                f"- **Total Duration**: {total_duration:.0f} min",
                f"- **Total Calories**: {total_calories} kcal",
                "",
                "### Activity Log"
            ]
            
            for act in activities:
                act_date = act['start_time'].strftime("%m/%d %H:%M") if act['start_time'] else ""
                distance_km = (act['distance_meters'] or 0) / 1000
                duration_min = (act['duration_sec'] or 0) / 60
                
                type_emoji = {
                    'running': '🏃',
                    'cycling': '🚴',
                    'swimming': '🏊',
                }.get(act['type'], '💪')
                
                exercise_lines.append(f"- {type_emoji} {act_date} {act.get('name', act['type'])}: {distance_km:.1f}km, {duration_min:.0f}min")
            
            content = content.replace('<!-- EXERCISE_SUMMARY_PLACEHOLDER -->', '\n'.join(exercise_lines))
        else:
            content = content.replace('<!-- EXERCISE_SUMMARY_PLACEHOLDER -->', '- No activities this week')
        
        # Write note
        note_path.write_text(content, encoding='utf-8')
        logger.info(f"Created weekly note: {note_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating weekly note: {e}")
        return False


def run_daily_note():
    """Create daily note for today."""
    tz = pytz.timezone(TZ)
    today = datetime.datetime.now(tz).date()
    create_daily_note(today)


def run_weekly_note():
    """Create weekly note if it's Sunday."""
    tz = pytz.timezone(TZ)
    today = datetime.datetime.now(tz).date()
    
    # Only create on Sunday (weekday() == 6)
    if today.weekday() == 6:
        create_weekly_note(today)


def main():
    logger.info("Worker Notes started.")
    
    # Ensure directories exist
    DAILY_PATH.mkdir(parents=True, exist_ok=True)
    WEEKLY_PATH.mkdir(parents=True, exist_ok=True)
    
    # Wait for other services
    time.sleep(10)
    
    # Create today's note on startup
    tz = pytz.timezone(TZ)
    today = datetime.datetime.now(tz).date()
    
    logger.info("Creating today's daily note...")
    create_daily_note(today)
    
    # If it's Sunday, also create weekly note
    if today.weekday() == 6:
        logger.info("It's Sunday - creating weekly note...")
        create_weekly_note(today)
    
    # Schedule daily note creation at 00:05
    schedule.every().day.at("00:05").do(run_daily_note)
    
    # Schedule weekly note creation on Sundays at 21:00
    schedule.every().sunday.at("21:00").do(run_weekly_note)
    
    logger.info("Scheduled: Daily note at 00:05, Weekly note on Sundays at 21:00")
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
