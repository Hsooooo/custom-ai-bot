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
- LLM calls are used for weekly draft + workout review messages.
- Later: add 3-turn guided Q&A + confirm->insert final plan.
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
import decimal


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-coach")

TZ = os.getenv("TZ", "Asia/Seoul")
TELEGRAM_BOT_TOKEN = os.getenv("COACH_TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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
        """
        CREATE TABLE IF NOT EXISTS workout_review_log (
          activity_id BIGINT PRIMARY KEY,
          sent_at TIMESTAMP,
          status TEXT NOT NULL DEFAULT 'pending',
          model TEXT,
          prompt_version TEXT,
          error TEXT
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


def _json_sanitize(obj: Any) -> Any:
    """Make objects JSON-serializable (dates/timestamps/decimals)."""
    if obj is None:
        return None
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_sanitize(v) for v in obj]
    return obj


def _read_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _render_prompt(template: str, data: Dict[str, Any]) -> str:
    import json

    return template.replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False, indent=2))


def _openai_generate(system: str, user: str) -> str:
    """Call OpenAI Chat Completions API with basic retry/backoff."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")

    import httpx

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
    }

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)

            # retry on rate limits
            if resp.status_code == 429:
                wait_s = 2 * (2**attempt)
                logger.warning(f"OpenAI rate limited (429). Retrying in {wait_s}s...")
                time.sleep(wait_s)
                continue

            resp.raise_for_status()
            data = resp.json()
            return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except Exception as e:
            last_err = e
            wait_s = 2 * (2**attempt)
            logger.warning(f"OpenAI call failed (attempt {attempt+1}/3): {e}. Retrying in {wait_s}s")
            time.sleep(wait_s)

    raise RuntimeError(f"OpenAI call failed after retries: {last_err}")


def draft_template(week_start: dt.date, race: Optional[Dict[str, Any]], injuries: List[Dict[str, Any]], summary14: Dict[str, Any], last_runs: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    data = {
        "week_start": str(week_start),
        "race": _json_sanitize(race),
        "injuries": _json_sanitize(injuries),
        "summary14": _json_sanitize(summary14),
        "last_runs": _json_sanitize(last_runs),
        "prompt_version": "weekly_plan_v1",
    }

    persona = _read_prompt("/app/prompts/persona.md")
    tmpl = _read_prompt("/app/prompts/weekly_plan.md")
    user = _render_prompt(tmpl, data)

    text = _openai_generate(system=persona, user=user)
    if not text:
        # fallback (should be rare)
        text = "주간 플랜 초안 생성 실패(LLM 응답 없음)."

    return text, data


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
    # Telegram message length limit safety
    if len(message) > 3800:
        message = message[:3800] + "\n…(truncated)"
    await bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=message)


def run_draft_job():
    local_now = tz_now()
    today = local_now.date()
    wk = next_week_start(today)

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

    import asyncio

    asyncio.run(send_telegram(text + f"\n\n(draft_id={draft_id})"))
    logger.info(f"Draft sent. draft_id={draft_id}")


def _mark_review_sent(activity_id: int, *, status: str, error: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO workout_review_log (activity_id, sent_at, status, model, prompt_version, error)
        VALUES (%s, NOW(), %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO UPDATE SET
          sent_at=EXCLUDED.sent_at,
          status=EXCLUDED.status,
          model=EXCLUDED.model,
          prompt_version=EXCLUDED.prompt_version,
          error=EXCLUDED.error;
        """,
        (activity_id, status, OPENAI_MODEL, "workout_review_v1", error),
    )
    conn.commit()
    cur.close()
    conn.close()


def _already_reviewed(activity_id: int) -> bool:
    row = select_one("SELECT activity_id, status FROM workout_review_log WHERE activity_id=%s", (activity_id,))
    if not row:
        return False
    # If previously failed, allow retry later (next poll)
    return row.get("status") == "sent"


def _build_review_input(activity_id: int) -> Dict[str, Any]:
    act = select_one(
        """
        SELECT activity_id, activity_name, start_time, duration_sec, distance_meters,
               avg_hr, max_hr, avg_pace
        FROM exercise_activity
        WHERE activity_id=%s
        """,
        (activity_id,),
    )

    laps = select_all(
        """
        SELECT lap_index, distance_meters, duration_sec, avg_pace, avg_hr, max_hr
        FROM exercise_lap
        WHERE activity_id=%s
        ORDER BY lap_index
        """,
        (activity_id,),
    )

    injuries = get_recent_injuries(5)
    race = get_next_race()

    return {
        "activity": _json_sanitize(act),
        "laps": _json_sanitize(laps),
        "injuries": _json_sanitize(injuries),
        "next_race": _json_sanitize(race),
        "tz": TZ,
    }


def run_review_poll():
    """Find newest running activities and send review once per activity."""
    logger.info("Review poll tick")
    latest = select_all(
        """
        SELECT activity_id
        FROM exercise_activity
        WHERE activity_type='running'
        ORDER BY start_time DESC NULLS LAST
        LIMIT 5
        """
    )
    for row in latest:
        aid = int(row["activity_id"])
        if _already_reviewed(aid):
            continue

        try:
            data = _build_review_input(aid)
            persona = _read_prompt("/app/prompts/persona.md")
            tmpl = _read_prompt("/app/prompts/workout_review.md")
            user = _render_prompt(tmpl, data)
            text = _openai_generate(system=persona, user=user)
            if not text:
                raise RuntimeError("empty LLM response")

            import asyncio

            asyncio.run(send_telegram(text))
            _mark_review_sent(aid, status="sent")
            logger.info(f"Workout review sent for activity_id={aid}")
            # only send 1 per poll to avoid spam bursts
            break
        except Exception as e:
            logger.error(f"Workout review failed for activity_id={aid}: {e}")
            _mark_review_sent(aid, status="failed", error=str(e)[:500])
            break


def main():
    logger.info("worker-coach started")
    time.sleep(10)
    init_db()

    # schedule: Sunday 23:00 weekly draft
    schedule.every().sunday.at("23:00").do(run_draft_job)
    logger.info("Scheduled: weekly draft Sunday 23:00")

    # schedule: workout review poll every 5 minutes
    schedule.every(5).minutes.do(run_review_poll)
    logger.info("Scheduled: workout review poll every 5 minutes")

    # Optional manual one-shots
    if os.getenv("COACH_RUN_DRAFT_ON_START") == "1":
        logger.warning("COACH_RUN_DRAFT_ON_START=1 -> running draft job once")
        try:
            run_draft_job()
        except Exception as e:
            logger.error(f"Draft job failed on start: {e}")

    if os.getenv("COACH_RUN_REVIEW_ON_START") == "1":
        logger.warning("COACH_RUN_REVIEW_ON_START=1 -> running review poll once")
        try:
            run_review_poll()
        except Exception as e:
            logger.error(f"Review poll failed on start: {e}")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
