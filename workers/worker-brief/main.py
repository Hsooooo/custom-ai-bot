import os
import time
import logging
import datetime
import asyncio
import psycopg2
import schedule
import pytz
from telegram import Bot

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


def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def get_health_data():
    """Get latest health data from database."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Get today and yesterday's data
    today = datetime.date.today()
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


def generate_briefing_message():
    """Generate morning briefing message."""
    try:
        health = get_health_data()
        activities = get_recent_activities(3)

        today = str(datetime.date.today())
        yesterday = str(datetime.date.today() - datetime.timedelta(days=1))

        # Use yesterday's sleep data (sleep is recorded for previous night)
        sleep_data = health.get(yesterday, health.get(today, {}))
        today_data = health.get(today, {})

        # Build message
        lines = ["🌅 *Good Morning!*\n"]

        # Sleep summary
        if sleep_data:
            sleep_hours = sleep_data.get('sleep_hours', 0)
            sleep_score = sleep_data.get('sleep_score', 0)
            lines.append(f"😴 *어제 수면*: {sleep_hours}시간 (점수: {sleep_score})")
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


async def send_briefing():
    """Send morning briefing via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        logger.error("Telegram credentials not configured.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        message = generate_briefing_message()

        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("Morning briefing sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send briefing: {e}")


def run_briefing():
    """Wrapper to run async send_briefing."""
    asyncio.run(send_briefing())


def main():
    logger.info("Worker Brief started.")

    # Wait for other services
    time.sleep(15)

    # Schedule morning briefing at 7:00 AM
    schedule.every().day.at("07:00").do(run_briefing)

    # Also schedule an evening summary at 22:00
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
