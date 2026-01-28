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

    # Per-lap (split) data (1km laps etc.)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exercise_lap (
            activity_id BIGINT NOT NULL,
            lap_index INTEGER NOT NULL,
            start_time_gmt TIMESTAMP,
            distance_meters NUMERIC,
            duration_sec NUMERIC,
            avg_speed_mps NUMERIC,
            avg_pace TEXT,
            avg_hr INTEGER,
            max_hr INTEGER,
            calories NUMERIC,
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (activity_id, lap_index)
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


def save_activity_laps(activity_id: int, laps: list[dict]):
    """Upsert per-lap splits for an activity."""
    if not laps:
        return

    conn = get_db_connection()
    cur = conn.cursor()

    for idx, lap in enumerate(laps, start=1):
        # Garmin returns lap duration in seconds (float) and distance in meters
        avg_speed = lap.get('averageSpeed')
        avg_pace = format_pace(avg_speed) if avg_speed else None

        cur.execute("""
            INSERT INTO exercise_lap (
                activity_id, lap_index, start_time_gmt,
                distance_meters, duration_sec, avg_speed_mps, avg_pace,
                avg_hr, max_hr, calories, raw_data
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (activity_id, lap_index) DO UPDATE SET
                start_time_gmt = EXCLUDED.start_time_gmt,
                distance_meters = EXCLUDED.distance_meters,
                duration_sec = EXCLUDED.duration_sec,
                avg_speed_mps = EXCLUDED.avg_speed_mps,
                avg_pace = EXCLUDED.avg_pace,
                avg_hr = EXCLUDED.avg_hr,
                max_hr = EXCLUDED.max_hr,
                calories = EXCLUDED.calories,
                raw_data = EXCLUDED.raw_data;
        """, (
            activity_id,
            idx,
            lap.get('startTimeGMT'),
            lap.get('distance'),
            lap.get('duration'),
            avg_speed,
            avg_pace,
            lap.get('averageHR'),
            lap.get('maxHR'),
            lap.get('calories'),
            Json(lap)
        ))

    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"Saved {len(laps)} laps for activity {activity_id}")


def format_pace(speed_mps):
    """Convert speed (m/s) to pace (min:sec/km)."""
    if not speed_mps or speed_mps <= 0:
        return None
    pace_sec_per_km = 1000 / float(speed_mps)
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

                # Fetch + save per-lap splits (pace, HR per lap, etc.)
                try:
                    splits = client.get_activity_splits(activity_id)
                    laps = splits.get('lapDTOs', []) if isinstance(splits, dict) else []
                    save_activity_laps(activity_id, laps)
                except Exception as e:
                    logger.warning(f"Failed to fetch/save laps for activity {activity_id}: {e}")

                # Generate markdown
                generate_activity_markdown(activity_data)

            except Exception as e:
                logger.error(f"Failed to process activity {act.get('activityId')}: {e}")
                continue

        logger.info(f"Synced {len(activities)} activities.")

    except Exception as e:
        logger.error(f"Failed to sync activities: {e}")


def get_recent_health_baseline(target_date: str, days: int = 7):
    """Compute a simple baseline from the previous N days.

    Returns dict with averages or None if insufficient history.
    """
    try:
        d = datetime.date.fromisoformat(target_date)
    except Exception:
        return None

    start = d - datetime.timedelta(days=days)
    end = d  # exclude target_date

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            AVG(sleep_hours)::float,
            AVG(resting_hr)::float,
            AVG(stress_level)::float,
            AVG(body_battery_min)::float,
            COUNT(*)
        FROM health_daily
        WHERE date >= %s AND date < %s
          AND sleep_hours IS NOT NULL
          AND resting_hr IS NOT NULL;
        """,
        (start, end),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    avg_sleep, avg_rhr, avg_stress, avg_bb_min, n = row
    if not n or n < 3:
        return None

    return {
        "days": int(n),
        "avg_sleep_hours": round(avg_sleep, 2) if avg_sleep is not None else None,
        "avg_resting_hr": round(avg_rhr, 1) if avg_rhr is not None else None,
        "avg_stress_level": round(avg_stress, 1) if avg_stress is not None else None,
        "avg_body_battery_min": round(avg_bb_min, 1) if avg_bb_min is not None else None,
    }


def generate_markdown(stats):
    date = stats['date']
    filename = os.path.join(OBSIDIAN_PATH, "Health", f"{date}.md")

    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    baseline = get_recent_health_baseline(date, days=7)

    insight_lines = []
    if baseline:
        sleep_delta = None
        rhr_delta = None

        if stats.get("sleep_hours") is not None and baseline.get("avg_sleep_hours") is not None:
            sleep_delta = round(float(stats["sleep_hours"]) - float(baseline["avg_sleep_hours"]), 1)

        if stats.get("resting_hr") is not None and baseline.get("avg_resting_hr") is not None:
            rhr_delta = round(float(stats["resting_hr"]) - float(baseline["avg_resting_hr"]), 1)

        # Simple fatigue flag: lower sleep + higher RHR vs baseline
        fatigue_flag = False
        if sleep_delta is not None and rhr_delta is not None:
            fatigue_flag = (sleep_delta <= -0.5) and (rhr_delta >= 3.0)

        insight_lines.append(f"- **7d Baseline (n={baseline['days']})**: sleep {baseline['avg_sleep_hours']}h, RHR {baseline['avg_resting_hr']} bpm")
        if sleep_delta is not None:
            insight_lines.append(f"- **Sleep vs 7d**: {sleep_delta:+.1f}h")
        if rhr_delta is not None:
            insight_lines.append(f"- **Resting HR vs 7d**: {rhr_delta:+.1f} bpm")
        if fatigue_flag:
            insight_lines.append("- **Fatigue signal**: sleep down + RHR up → 오늘은 강도 낮추고 회복(수면/수분/가벼운 유산소) 추천")

    insights_block = "\n".join(insight_lines) if insight_lines else "- (Not enough history yet)"

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

## Insights (simple)
{insights_block}

## Raw Info
Generated at {datetime.datetime.now().strftime("%H:%M:%S")}
"""

    with open(filename, 'w') as f:
        f.write(content)
    logger.info(f"Generated markdown for {date}")

def login_garmin_with_retry():
    """Login to Garmin Connect with retry logic.

    Important: do NOT call client.garth.load() directly.
    garminconnect.Garmin.login(tokenstore=...) both loads tokens AND populates
    client.display_name/full_name; without that, some endpoints (e.g. user summary)
    will call /daily/None and return 403.
    """
    import garth

    token_dir = "/app/.garth"
    os.makedirs(token_dir, exist_ok=True)

    client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)

    # Try loading existing session first (via Garmin.login so display_name is set)
    try:
        client.login(tokenstore=token_dir)
        if not getattr(client, "display_name", None):
            raise RuntimeError("Garmin session loaded but display_name is empty")
        # Validate session by hitting an authenticated endpoint
        client.get_user_summary(datetime.date.today().isoformat())
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
            if not getattr(client, "display_name", None):
                raise RuntimeError("Garmin login succeeded but display_name is empty")
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
                # NOTE: Garmin sleep payload key can be dailySleepDto (older) or dailySleepDTO (newer)
                sleep_dto = sleep_data.get('dailySleepDto') or sleep_data.get('dailySleepDTO') or {}

                sleep_seconds = sleep_dto.get('sleepTimeSeconds', 0) or 0
                sleep_hours = round(sleep_seconds / 3600, 1)

                # Sleep score can vary by device/account; try common locations
                sleep_score = (
                    sleep_dto.get('sleepScoreValue')
                    or (sleep_dto.get('sleepScores') or {}).get('overall', {}).get('value')
                    or 0
                )

                stats = {
                    'date': sync_date_str,
                    'sleep_hours': sleep_hours,
                    'sleep_score': int(sleep_score) if sleep_score is not None else 0,
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
