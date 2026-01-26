import os
import time
import json
import logging
import datetime
import asyncio
import functools
from garminconnect import Garmin
import psycopg2
from psycopg2.extras import Json
import schedule

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger('worker-garmin')

# Environment Variables
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
OBSIDIAN_PATH = "/obsidian"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 5  # seconds


def retry_with_backoff(max_retries=MAX_RETRIES, base_delay=RETRY_DELAY_BASE):
    """Decorator for retry with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
            logger.error(f"{func.__name__} failed after {max_retries} attempts")
            raise last_exception
        return wrapper
    return decorator


async def send_telegram_alert(message: str):
    """Send alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        return

    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=f"⚠️ Worker-Garmin Alert\n\n{message}")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


def notify_error(message: str):
    """Sync wrapper for sending error notifications."""
    try:
        asyncio.run(send_telegram_alert(message))
    except Exception:
        pass


@retry_with_backoff(max_retries=3, base_delay=5)
def get_db_connection():
    """Get database connection with retry."""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=10
    )
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create tables if not exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS health_daily (
            date DATE PRIMARY KEY,
            sleep_hours NUMERIC,
            sleep_score INTEGER,
            resting_hr INTEGER,
            hrv_status TEXT,
            stress_level INTEGER,
            body_battery_max INTEGER,
            body_battery_min INTEGER,
            raw_data JSONB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exercise_activity (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Ensure missing columns exist (for migration)
    cur.execute("ALTER TABLE exercise_activity ADD COLUMN IF NOT EXISTS activity_name TEXT;")
    cur.execute("ALTER TABLE exercise_activity ADD COLUMN IF NOT EXISTS avg_hr INTEGER;")
    cur.execute("ALTER TABLE exercise_activity ADD COLUMN IF NOT EXISTS max_hr INTEGER;")
    cur.execute("ALTER TABLE exercise_activity ADD COLUMN IF NOT EXISTS avg_pace TEXT;")
    cur.execute("ALTER TABLE exercise_activity ADD COLUMN IF NOT EXISTS elevation_gain NUMERIC;")
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database initialized.")

def save_daily_stats(stats):
    conn = get_db_connection()
    cur = conn.cursor()
    
    date = stats['date']
    
    cur.execute("""
        INSERT INTO health_daily (
            date, sleep_hours, sleep_score, resting_hr, hrv_status, 
            stress_level, body_battery_max, body_battery_min, raw_data, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (date) DO UPDATE SET
            sleep_hours = EXCLUDED.sleep_hours,
            sleep_score = EXCLUDED.sleep_score,
            resting_hr = EXCLUDED.resting_hr,
            hrv_status = EXCLUDED.hrv_status,
            stress_level = EXCLUDED.stress_level,
            body_battery_max = EXCLUDED.body_battery_max,
            body_battery_min = EXCLUDED.body_battery_min,
            raw_data = EXCLUDED.raw_data,
            updated_at = NOW();
    """, (
        date, stats['sleep_hours'], stats['sleep_score'], stats['resting_hr'], 
        stats['hrv_status'], stats['stress_level'], stats['body_battery_max'], 
        stats['body_battery_min'], Json(stats)
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Saved daily stats for {date}")

def save_activity(activity):
    """Save exercise activity to database."""
    conn = get_db_connection()
    cur = conn.cursor()

    activity_id = activity['activity_id']

    cur.execute("""
        INSERT INTO exercise_activity (
            activity_id, activity_type, activity_name, start_time, duration_sec,
            distance_meters, avg_hr, max_hr, avg_pace, calories, elevation_gain, raw_data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO UPDATE SET
            activity_type = EXCLUDED.activity_type,
            activity_name = EXCLUDED.activity_name,
            duration_sec = EXCLUDED.duration_sec,
            distance_meters = EXCLUDED.distance_meters,
            avg_hr = EXCLUDED.avg_hr,
            max_hr = EXCLUDED.max_hr,
            avg_pace = EXCLUDED.avg_pace,
            calories = EXCLUDED.calories,
            elevation_gain = EXCLUDED.elevation_gain,
            raw_data = EXCLUDED.raw_data;
    """, (
        activity_id,
        activity.get('activity_type'),
        activity.get('activity_name'),
        activity.get('start_time'),
        activity.get('duration_sec'),
        activity.get('distance_meters'),
        activity.get('avg_hr'),
        activity.get('max_hr'),
        activity.get('avg_pace'),
        activity.get('calories'),
        activity.get('elevation_gain'),
        Json(activity.get('raw_data', {}))
    ))

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Saved activity {activity_id}: {activity.get('activity_name')}")


def format_pace(speed_mps):
    """Convert speed (m/s) to pace (min:sec/km)."""
    if not speed_mps or speed_mps <= 0:
        return None
    pace_sec_per_km = 1000 / speed_mps
    minutes = int(pace_sec_per_km // 60)
    seconds = int(pace_sec_per_km % 60)
    return f"{minutes}:{seconds:02d}"


def generate_activity_markdown(activity):
    """Generate markdown file for exercise activity."""
    start_time = activity.get('start_time')
    if not start_time:
        return

    date_str = start_time[:10]  # YYYY-MM-DD
    activity_type = activity.get('activity_type', 'exercise')
    activity_id = activity.get('activity_id')

    filename = os.path.join(OBSIDIAN_PATH, "Exercise", f"{date_str}_{activity_type}_{activity_id}.md")
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Format distance
    distance_km = activity.get('distance_meters', 0) / 1000 if activity.get('distance_meters') else 0

    # Format duration
    duration_sec = activity.get('duration_sec', 0)
    duration_min = duration_sec // 60
    duration_hours = duration_min // 60
    duration_remaining_min = duration_min % 60

    if duration_hours > 0:
        duration_str = f"{duration_hours}h {duration_remaining_min}m"
    else:
        duration_str = f"{duration_min}m"

    content = f"""# {activity.get('activity_name', activity_type)} - {date_str}

## Summary
- **Type**: {activity_type}
- **Duration**: {duration_str}
- **Distance**: {distance_km:.2f} km
- **Calories**: {activity.get('calories', 0)} kcal

## Heart Rate
- **Average HR**: {activity.get('avg_hr', 'N/A')} bpm
- **Max HR**: {activity.get('max_hr', 'N/A')} bpm

## Performance
- **Pace**: {activity.get('avg_pace', 'N/A')} /km
- **Elevation Gain**: {activity.get('elevation_gain', 0):.0f} m

---
Activity ID: {activity_id}
Generated at {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    with open(filename, 'w') as f:
        f.write(content)
    logger.info(f"Generated exercise markdown: {filename}")


def sync_activities(client):
    """Sync recent exercise activities from Garmin Connect."""
    logger.info("Syncing exercise activities...")

    try:
        # Get last 10 activities (adjust as needed)
        activities = client.get_activities(0, 10)

        if not activities:
            logger.info("No activities found.")
            return

        for act in activities:
            try:
                activity_id = act.get('activityId')
                if not activity_id:
                    continue

                # Extract activity data
                activity_data = {
                    'activity_id': activity_id,
                    'activity_type': act.get('activityType', {}).get('typeKey', 'unknown'),
                    'activity_name': act.get('activityName', ''),
                    'start_time': act.get('startTimeLocal'),
                    'duration_sec': int(act.get('duration', 0)),
                    'distance_meters': act.get('distance'),
                    'avg_hr': act.get('averageHR'),
                    'max_hr': act.get('maxHR'),
                    'avg_pace': format_pace(act.get('averageSpeed')),
                    'calories': act.get('calories'),
                    'elevation_gain': act.get('elevationGain'),
                    'raw_data': act
                }

                # Save to DB
                save_activity(activity_data)

                # Generate markdown
                generate_activity_markdown(activity_data)

            except Exception as e:
                logger.error(f"Failed to process activity {act.get('activityId')}: {e}")
                continue

        logger.info(f"Synced {len(activities)} activities.")

    except Exception as e:
        logger.error(f"Failed to sync activities: {e}")


def generate_markdown(stats):
    date = stats['date']
    filename = os.path.join(OBSIDIAN_PATH, "Health", f"{date}.md")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    content = f"""# Health Summary - {date}

## Sleep
- **Duration**: {stats['sleep_hours']} hours
- **Score**: {stats['sleep_score']}

## Body Battery & Stress
- **Max BB**: {stats['body_battery_max']}
- **Min BB**: {stats['body_battery_min']}
- **Avg Stress**: {stats['stress_level']}

## Heart Rate
- **Resting HR**: {stats['resting_hr']}
- **HRV Status**: {stats['hrv_status']}

## Raw Info
Generated at {datetime.datetime.now().strftime("%H:%M:%S")}
"""
    with open(filename, 'w') as f:
        f.write(content)
    logger.info(f"Generated markdown for {date}")

def login_garmin_with_retry():
    """Login to Garmin Connect with retry logic."""
    import garth
    token_dir = "/app/.garth"
    os.makedirs(token_dir, exist_ok=True)

    client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)

    # Try loading existing session first
    try:
        client.garth.load(token_dir)
        # Validate session by making a simple request
        client.get_full_name()
        logger.info("Existing Garmin session loaded and validated.")
        return client
    except Exception as e:
        logger.info(f"Session invalid or expired: {e}")

    # Fresh login with retry
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Attempting fresh Garmin login (attempt {attempt + 1}/{MAX_RETRIES})...")
            client.login()
            client.garth.dump(token_dir)
            logger.info("New Garmin session saved.")
            return client
        except Exception as e:
            last_exception = e
            delay = RETRY_DELAY_BASE * (2 ** attempt)
            logger.warning(f"Garmin login failed: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)

    error_msg = f"Garmin login failed after {MAX_RETRIES} attempts: {last_exception}"
    logger.error(error_msg)
    notify_error(error_msg)
    raise last_exception


def run_sync():
    logger.info("Starting Garmin Sync...")
    sync_errors = []

    try:
        # 1. Login with session management
        client = login_garmin_with_retry()
        logger.info("Garmin login successful.")
        
        # 2. Define Date Range (Sync last 3 days to ensure consistency)
        today = datetime.date.today()
        date_range = [today - datetime.timedelta(days=i) for i in range(3)]
        
        for sync_date in reversed(date_range):
            sync_date_str = sync_date.isoformat()
            logger.info(f"Fetching data for {sync_date_str}...")
            
            try:
                # User Summary (Stress, Body Battery, RHR)
                summary = client.get_user_summary(sync_date_str)
                # Sleep Data
                sleep_data = client.get_sleep_data(sync_date_str)
                # HRV Data
                try:
                    hrv_data = client.get_hrv_data(sync_date_str)
                    hrv_status = hrv_data.get('hrvSummary', {}).get('status', 'N/A')
                except:
                    hrv_status = 'N/A'

                # Extract stats
                sleep_seconds = sleep_data.get('dailySleepDto', {}).get('sleepTimeSeconds', 0)
                sleep_hours = round(sleep_seconds / 3600, 1)
                sleep_score = sleep_data.get('dailySleepDto', {}).get('sleepScoreValue', 0)
                
                stats = {
                    'date': sync_date_str,
                    'sleep_hours': sleep_hours,
                    'sleep_score': sleep_score,
                    'resting_hr': summary.get('restingHeartRate', 0),
                    'hrv_status': hrv_status,
                    'stress_level': summary.get('averageStressLevel', 0),
                    'body_battery_max': summary.get('bodyBatteryMostRecentValue', 0),
                    'body_battery_min': 0
                }
                
                if 'bodyBatteryValuesArray' in summary:
                    bb_values = [item[1] for item in summary['bodyBatteryValuesArray'] if item[1] is not None]
                    if bb_values:
                        stats['body_battery_max'] = max(bb_values)
                        stats['body_battery_min'] = min(bb_values)
                
                # 4. Save to DB & Generate Markdown
                save_daily_stats(stats)
                generate_markdown(stats)
                
            except Exception as e:
                error_msg = f"Failed to fetch data for {sync_date_str}: {e}"
                logger.error(error_msg)
                sync_errors.append(error_msg)
                continue

        # Sync exercise activities
        try:
            sync_activities(client)
        except Exception as e:
            error_msg = f"Failed to sync activities: {e}"
            logger.error(error_msg)
            sync_errors.append(error_msg)

        # Report sync completion
        if sync_errors:
            error_summary = f"Sync completed with {len(sync_errors)} error(s):\n" + "\n".join(sync_errors[:5])
            notify_error(error_summary)
            logger.warning(error_summary)
        else:
            logger.info("Sync completed successfully with no errors.")

    except Exception as e:
        import traceback
        error_msg = f"Critical sync error: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        notify_error(error_msg)

def main():
    logger.info("Worker Garmin started.")
    
    # Wait for DB to be ready
    time.sleep(10) 
    init_db()
    
    # Schedule
    schedule.every(4).hours.do(run_sync)
    
    # Run once on startup
    run_sync()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
