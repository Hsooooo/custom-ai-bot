import os
import sys
import time
import logging
import datetime
import asyncio
import psycopg2
import schedule
import pytz
from telegram import Bot

# Add shared modules to path
sys.path.insert(0, '/app/shared')

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('worker-brief')

# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
TZ = os.getenv("TZ", "Asia/Seoul")

# Import external services
try:
    from external_services import (
        get_weather, format_weather,
        get_calendar_events, format_calendar_events,
        get_github_activity, format_github_activity
    )
    EXTERNAL_SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"External services not available: {e}")
    EXTERNAL_SERVICES_AVAILABLE = False

# Import Redis utilities
try:
    from redis_utils import (
        is_redis_available, cache_get, cache_set,
        CacheKeys, weather_limiter, github_limiter
    )
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis utilities not available")


def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def _tz_today() -> datetime.date:
    tz = pytz.timezone(TZ)
    return datetime.datetime.now(tz).date()


def get_health_data(today: datetime.date | None = None):
    """Get latest health data from database.

    Note:
    - Garmin sleep for "last night" is typically stored on *today's* date.
    - We compute dates in configured TZ (default Asia/Seoul) to avoid UTC drift.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Get today and yesterday's data (TZ-aware)
    today = today or _tz_today()
    yesterday = today - datetime.timedelta(days=1)

    cur.execute("""
        SELECT date, sleep_hours, sleep_score, resting_hr, hrv_status,
               stress_level, body_battery_max, body_battery_min
        FROM health_daily
        WHERE date IN (%s, %s)
        ORDER BY date DESC
    """, (today, yesterday))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {}
    for row in rows:
        result[str(row[0])] = {
            'date': str(row[0]),
            'sleep_hours': row[1],
            'sleep_score': row[2],
            'resting_hr': row[3],
            'hrv_status': row[4],
            'stress_level': row[5],
            'body_battery_max': row[6],
            'body_battery_min': row[7]
        }

    return result


def get_recent_activities(limit=3):
    """Get recent exercise activities."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT activity_type, activity_name, start_time, duration_sec,
               distance_meters, avg_hr, avg_pace, calories
        FROM exercise_activity
        ORDER BY start_time DESC
        LIMIT %s
    """, (limit,))

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
            'avg_hr': row[5],
            'avg_pace': row[6],
            'calories': row[7]
        })

    return activities


def format_duration(seconds):
    """Format duration in seconds to human readable."""
    if not seconds:
        return "N/A"
    minutes = seconds // 60
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    return f"{minutes}m"


async def get_external_data():
    """Fetch all external service data concurrently."""
    weather_data = None
    calendar_events = []
    github_activity = {}
    
    if not EXTERNAL_SERVICES_AVAILABLE:
        return weather_data, calendar_events, github_activity
    
    try:
        # Check rate limits and cache
        tasks = []
        
        # Weather (with caching)
        if REDIS_AVAILABLE and is_redis_available():
            cached_weather = cache_get(CacheKeys.WEATHER)
            if cached_weather:
                weather_data = cached_weather
            elif weather_limiter.allow():
                tasks.append(('weather', get_weather()))
        else:
            tasks.append(('weather', get_weather()))
        
        # Calendar
        tasks.append(('calendar', get_calendar_events()))
        
        # GitHub (with rate limiting)
        if REDIS_AVAILABLE and is_redis_available():
            cached_github = cache_get(CacheKeys.GITHUB)
            if cached_github:
                github_activity = cached_github
            elif github_limiter.allow():
                tasks.append(('github', get_github_activity()))
        else:
            tasks.append(('github', get_github_activity()))
        
        # Execute tasks concurrently
        if tasks:
            results = await asyncio.gather(
                *[task[1] for task in tasks],
                return_exceptions=True
            )
            
            for i, (name, _) in enumerate(tasks):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch {name}: {result}")
                    continue
                
                if name == 'weather' and result:
                    weather_data = result
                    if REDIS_AVAILABLE and is_redis_available():
                        cache_set(CacheKeys.WEATHER, result, ttl_seconds=1800)  # 30 min
                elif name == 'calendar':
                    calendar_events = result or []
                elif name == 'github' and result:
                    github_activity = result
                    if REDIS_AVAILABLE and is_redis_available():
                        cache_set(CacheKeys.GITHUB, result, ttl_seconds=900)  # 15 min
        
    except Exception as e:
        logger.error(f"Error fetching external data: {e}")
    
    return weather_data, calendar_events, github_activity


async def generate_briefing_message_async():
    """Generate morning briefing message with external data."""
    try:
        tz = pytz.timezone(TZ)
        now = datetime.datetime.now(tz)
        today_date = now.date()
        yesterday_date = today_date - datetime.timedelta(days=1)

        health = get_health_data(today=today_date)
        activities = get_recent_activities(3)

        # Fetch external data
        weather_data, calendar_events, github_activity = await get_external_data()

        today = str(today_date)
        yesterday = str(yesterday_date)

        # Use today's row for sleep if available; if not, fall back to yesterday BUT label it clearly.
        sleep_data = health.get(today) or health.get(yesterday) or {}
        sleep_date = today if health.get(today) else (yesterday if health.get(yesterday) else None)

        today_data = health.get(today, {})

        # Build message
        is_morning = now.hour < 12

        if is_morning:
            lines = ["🌅 *Good Morning!*\n"]
        else:
            lines = ["🌙 *Evening Summary*\n"]

        # Weather section (NEW)
        if EXTERNAL_SERVICES_AVAILABLE and weather_data:
            lines.append(format_weather(weather_data))
            lines.append("")
        
        # Calendar section (NEW)
        if EXTERNAL_SERVICES_AVAILABLE and calendar_events:
            lines.append(format_calendar_events(calendar_events))
            lines.append("")

        # Sleep summary
        if sleep_data and sleep_date:
            sleep_hours = sleep_data.get('sleep_hours', 0)
            sleep_score = sleep_data.get('sleep_score', 0)
            label = "오늘 수면" if sleep_date == today else "어제 수면"
            # Always show the date to avoid confusion.
            lines.append(f"😴 *{label}* ({sleep_date}): {sleep_hours}시간 (점수: {sleep_score})")
            if (not is_morning) and sleep_date != today:
                lines.append("   (참고: 오늘 수면 데이터가 아직 동기화되지 않아 어제 값을 표시했어요)")
        else:
            lines.append("😴 *수면 데이터*: 없음")

        # Body Battery
        if today_data:
            bb_max = today_data.get('body_battery_max', 0)
            stress = today_data.get('stress_level', 0)
            rhr = today_data.get('resting_hr', 0)
            hrv = today_data.get('hrv_status', 'N/A')

            # Body battery status
            if bb_max >= 80:
                bb_emoji = "🔋"
                bb_status = "충전 완료!"
            elif bb_max >= 50:
                bb_emoji = "🔋"
                bb_status = "적당함"
            else:
                bb_emoji = "🪫"
                bb_status = "휴식 필요"

            lines.append(f"{bb_emoji} *Body Battery*: {bb_max}% → {bb_status}")
            lines.append(f"💓 *안정시 심박수*: {rhr} bpm (HRV: {hrv})")
            lines.append(f"😰 *평균 스트레스*: {stress}")
        else:
            lines.append("📊 *오늘 데이터*: 아직 동기화 안됨")

        # Recent activities
        if activities:
            lines.append("\n🏃 *최근 운동*:")
            for act in activities[:3]:
                act_date = act['start_time'].strftime("%m/%d") if act['start_time'] else ""
                distance_km = (act['distance_meters'] or 0) / 1000
                duration = format_duration(act['duration_sec'])
                pace = act['avg_pace'] or ""

                if act['type'] == 'running':
                    emoji = "🏃"
                    detail = f"{distance_km:.1f}km"
                    if pace:
                        detail += f" ({pace}/km)"
                elif act['type'] == 'cycling':
                    emoji = "🚴"
                    detail = f"{distance_km:.1f}km"
                elif act['type'] == 'swimming':
                    emoji = "🏊"
                    detail = f"{distance_km*1000:.0f}m"
                else:
                    emoji = "💪"
                    detail = duration

                lines.append(f"  {emoji} {act_date} {act.get('name', act['type'])}: {detail}")

        # GitHub activity (NEW)
        if EXTERNAL_SERVICES_AVAILABLE and github_activity:
            github_str = format_github_activity(github_activity)
            if github_str:
                lines.append("")
                lines.append(github_str)

        # Add motivational note based on data
        lines.append("\n---")
        if today_data and today_data.get('body_battery_max', 0) >= 80:
            lines.append("✨ 오늘 컨디션 좋아 보여요! 좋은 하루 되세요!")
        elif sleep_data and sleep_data.get('sleep_hours', 0) < 6:
            lines.append("😴 수면이 부족해요. 오늘은 무리하지 마세요.")
        else:
            lines.append("💪 좋은 하루 되세요!")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to generate briefing: {e}")
        return f"⚠️ 브리핑 생성 실패: {e}"


def generate_briefing_message():
    """Sync wrapper for backward compatibility."""
    return asyncio.run(generate_briefing_message_async())


async def send_briefing():
    """Send morning briefing via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        logger.error("Telegram credentials not configured.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        message = await generate_briefing_message_async()

        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("Briefing sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send briefing: {e}")


def run_briefing():
    """Wrapper to run async send_briefing."""
    asyncio.run(send_briefing())


def main():
    logger.info("Worker Brief started.")
    
    # Log external service status
    if EXTERNAL_SERVICES_AVAILABLE:
        logger.info("External services: Weather, Calendar, GitHub - Available")
    else:
        logger.warning("External services: Not available")
    
    if REDIS_AVAILABLE:
        try:
            if is_redis_available():
                logger.info("Redis: Connected")
            else:
                logger.warning("Redis: Not available")
        except:
            logger.warning("Redis: Not available")
    else:
        logger.warning("Redis: Not available")

    # Wait for other services
    time.sleep(15)

    # Schedule morning briefing at 7:00 AM
    schedule.every().day.at("07:00").do(run_briefing)

    # Also schedule an evening summary at 22:00
    # Note: Garmin sync may complete slightly after 22:00 depending on runtime; sleep section
    # will fall back to yesterday with an explicit note if today's row isn't available yet.
    schedule.every().day.at("22:00").do(run_briefing)

    logger.info("Scheduled briefings: 07:00, 22:00")

    # For testing: send briefing on startup if it's between 6-8 AM or 21-23
    tz = pytz.timezone(TZ)
    now = datetime.datetime.now(tz)
    hour = now.hour

    if 6 <= hour <= 8 or 21 <= hour <= 23:
        logger.info("Sending startup briefing...")
        run_briefing()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
