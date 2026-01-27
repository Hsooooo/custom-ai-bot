"""worker-coach (MVP)

Goal (MVP):
- Every Sunday 23:00 (Asia/Seoul), if next week's plan is not confirmed and no draft exists,
  generate a draft weekly plan and send it to the COACH Telegram bot.
- Include richer inputs:
  - 14d running summary
  - last 2 runs detail (avg/max HR + laps pace)
  - recent injury logs
  - next race event

Notes:
- This MVP intentionally avoids LLM calls.
- Later: add LLM prompt + 3-turn guided Q&A + confirm->insert final plan.
"""

import os
import time
import logging
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import schedule
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor, Json


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-coach")

TZ = os.getenv("TZ", "Asia/Seoul")
TELEGRAM_BOT_TOKEN = os.getenv("COACH_TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")


def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def init_db():
    """Create coach tables if missing."""
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS training_plan_weekly (
          id BIGSERIAL PRIMARY KEY,
          week_start DATE NOT NULL,
          race_event_id BIGINT,
          raw_plan_text TEXT,
          prompt_version TEXT,
          model TEXT,
          created_at TIMESTAMP DEFAULT NOW(),
          UNIQUE (week_start)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS training_plan_day (
          id BIGSERIAL PRIMARY KEY,
          week_start DATE NOT NULL,
          plan_date DATE NOT NULL,
          session_type TEXT,
          duration_min INTEGER,
          distance_km NUMERIC,
          intensity TEXT,
          notes TEXT,
          created_at TIMESTAMP DEFAULT NOW(),
          UNIQUE (plan_date)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS training_plan_draft_weekly (
          id BIGSERIAL PRIMARY KEY,
          week_start DATE NOT NULL,
          version INTEGER NOT NULL DEFAULT 1,
          draft_text TEXT,
          draft_data JSONB,
          status TEXT NOT NULL DEFAULT 'draft',
          created_at TIMESTAMP DEFAULT NOW(),
          UNIQUE (week_start, version)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS coach_session (
          id BIGSERIAL PRIMARY KEY,
          week_start DATE NOT NULL,
          turn_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'draft',
          last_message TEXT,
          updated_at TIMESTAMP DEFAULT NOW(),
          UNIQUE (week_start)
        );
        """,
    ]

    conn = get_db_connection()
    cur = conn.cursor()
    for stmt in ddl:
        cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Coach DB tables ensured.")


def tz_now() -> dt.datetime:
    return dt.datetime.now(pytz.timezone(TZ))


def next_week_start(today: dt.date) -> dt.date:
    """Return next week's Monday date in local TZ."""
    # weekday: Mon=0..Sun=6
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    return today + dt.timedelta(days=days_until_next_monday)


def select_one(query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def select_all(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def has_confirmed_plan(week_start: dt.date) -> bool:
    row = select_one("SELECT id FROM training_plan_weekly WHERE week_start=%s", (week_start,))
    return row is not None


def has_draft(week_start: dt.date) -> bool:
    row = select_one(
        "SELECT id FROM training_plan_draft_weekly WHERE week_start=%s AND status='draft' ORDER BY version DESC LIMIT 1",
        (week_start,),
    )
    return row is not None


def get_next_race() -> Optional[Dict[str, Any]]:
    return select_one(
        """
        SELECT id, name, race_date, distance_km, target_time_sec, location
        FROM race_event
        WHERE race_date >= CURRENT_DATE
        ORDER BY race_date ASC
        LIMIT 1
        """
    )


def get_recent_injuries(limit: int = 5) -> List[Dict[str, Any]]:
    return select_all(
        """
        SELECT date, body_part, side, pain_score, pain_type, trigger, notes
        FROM injury_log
        ORDER BY date DESC, created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_last_runs(limit: int = 2) -> List[Dict[str, Any]]:
    runs = select_all(
        """
        SELECT activity_id, activity_type, activity_name, start_time, duration_sec,
               distance_meters, avg_hr, max_hr, avg_pace
        FROM exercise_activity
        WHERE activity_type='running'
        ORDER BY start_time DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )

    # add laps
    for r in runs:
        laps = select_all(
            """
            SELECT lap_index, distance_meters, duration_sec, avg_pace, avg_hr, max_hr
            FROM exercise_lap
            WHERE activity_id=%s
            ORDER BY lap_index
            """,
            (r["activity_id"],),
        )
        r["laps"] = laps
    return runs


def get_running_summary_14d() -> Dict[str, Any]:
    rows = select_all(
        """
        SELECT
          COUNT(*)::int AS run_count,
          COALESCE(SUM(distance_meters),0) AS total_m,
          COALESCE(SUM(duration_sec),0) AS total_sec,
          COALESCE(MAX(distance_meters),0) AS max_run_m,
          COALESCE(MAX(duration_sec),0) AS max_run_sec
        FROM exercise_activity
        WHERE activity_type='running'
          AND start_time >= (NOW() - INTERVAL '14 days')
        """
    )
    return rows[0] if rows else {}


def fmt_hms(seconds: Optional[int]) -> str:
    if not seconds:
        return "0:00:00"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


def draft_template(week_start: dt.date, race: Optional[Dict[str, Any]], injuries: List[Dict[str, Any]], summary14: Dict[str, Any], last_runs: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    lines: List[str] = []
    lines.append("🧑‍🏫 Weekly Coach Plan (DRAFT)")
    lines.append(f"Week start: {week_start} (Mon)")

    if race:
        tgt = fmt_hms(race.get("target_time_sec"))
        lines.append("")
        lines.append("🏁 Next race")
        lines.append(f"- {race.get('race_date')} {race.get('name')} {race.get('distance_km')}km @ {race.get('location','')}")
        lines.append(f"- Target time: {tgt}")

    if injuries:
        lines.append("")
        lines.append("🩹 Recent injuries (latest 5)")
        for inj in injuries:
            lines.append(
                f"- {inj.get('date')} {inj.get('side','')}/{inj.get('body_part')} pain {inj.get('pain_score')}/10 ({inj.get('pain_type','')}) trigger={inj.get('trigger','')}"
            )

    lines.append("")
    lines.append("📈 Running summary (last 14d)")
    total_km = float(summary14.get("total_m", 0) or 0) / 1000.0
    total_h = int(summary14.get("total_sec", 0) or 0) // 3600
    lines.append(f"- runs: {summary14.get('run_count',0)} | distance: {total_km:.1f}km | time: {total_h}h")

    if last_runs:
        lines.append("")
        lines.append("🏃 Last 2 runs (detail)")
        for r in last_runs:
            dist_km = float(r.get("distance_meters") or 0) / 1000.0
            dur = fmt_hms(r.get("duration_sec"))
            lines.append(
                f"- {r.get('start_time')} {r.get('activity_name','running')} {dist_km:.2f}km / {dur} | HR avg {r.get('avg_hr')} max {r.get('max_hr')} | pace {r.get('avg_pace') or ''}"
            )
            laps = r.get("laps") or []
            if laps:
                # show first 6 laps to keep message small
                for lap in laps[:6]:
                    lines.append(
                        f"  lap{lap.get('lap_index')}: {lap.get('avg_pace','')} HR {lap.get('avg_hr','')}/{lap.get('max_hr','')} dur {int(float(lap.get('duration_sec') or 0))}s"
                    )
                if len(laps) > 6:
                    lines.append(f"  … ({len(laps)} laps total)")

    lines.append("")
    lines.append("❓ Quick questions (reply as 1)…, 2)…)")
    lines.append("1) Any days/times you CANNOT run next week?")
    lines.append("2) Current pain status (0-10 + body part)?")
    lines.append("3) Preferred number of runs next week (3/4/5/6)?")
    lines.append("4) Long run day preference (Sat/Sun/none)?")

    lines.append("")
    lines.append("Reply with your answers. We'll iterate up to 3 times and then confirm.")

    data = {
        "week_start": str(week_start),
        "race": race,
        "injuries": injuries,
        "summary14": summary14,
        "last_runs": last_runs,
        "prompt_version": "mvp-template-v1",
    }

    return "\n".join(lines), data


def save_draft(week_start: dt.date, text: str, data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    # next version
    cur.execute(
        "SELECT COALESCE(MAX(version),0)+1 FROM training_plan_draft_weekly WHERE week_start=%s",
        (week_start,),
    )
    version = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO training_plan_draft_weekly (week_start, version, draft_text, draft_data, status)
        VALUES (%s,%s,%s,%s,'draft')
        RETURNING id
        """,
        (week_start, int(version), text, Json(data)),
    )
    draft_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO coach_session (week_start, turn_count, status, last_message, updated_at)
        VALUES (%s, 0, 'draft', %s, NOW())
        ON CONFLICT (week_start) DO UPDATE SET
          status='draft',
          last_message=EXCLUDED.last_message,
          updated_at=NOW();
        """,
        (week_start, text[:4000]),
    )

    conn.commit()
    cur.close()
    conn.close()
    return int(draft_id)


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        logger.error("COACH_TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_ID not configured")
        return

    from telegram import Bot

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=message)


def run_draft_job():
    local_now = tz_now()
    today = local_now.date()
    wk = next_week_start(today)

    # only run on Sunday 23:00 schedule, but guard anyway
    logger.info(f"Draft job tick: now={local_now.isoformat()} next_week_start={wk}")

    if has_confirmed_plan(wk):
        logger.info("Skip: confirmed plan already exists")
        return
    if has_draft(wk):
        logger.info("Skip: draft already exists")
        return

    race = get_next_race()
    injuries = get_recent_injuries(5)
    summary14 = get_running_summary_14d()
    last_runs = get_last_runs(2)

    text, data = draft_template(wk, race, injuries, summary14, last_runs)
    draft_id = save_draft(wk, text, data)

    # send
    import asyncio

    asyncio.run(send_telegram(text + f"\n\n(draft_id={draft_id})"))
    logger.info(f"Draft sent. draft_id={draft_id}")


def main():
    logger.info("worker-coach started")
    time.sleep(10)
    init_db()

    # schedule: Sunday 23:00
    schedule.every().sunday.at("23:00").do(run_draft_job)
    logger.info("Scheduled: weekly draft Sunday 23:00")

    # Optional: manual one-shot for testing (won't run unless explicitly enabled)
    if os.getenv("COACH_RUN_DRAFT_ON_START") == "1":
        logger.warning("COACH_RUN_DRAFT_ON_START=1 -> running draft job once")
        try:
            run_draft_job()
        except Exception as e:
            logger.error(f"Draft job failed on start: {e}")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
