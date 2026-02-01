from __future__ import annotations

import os
from datetime import datetime

import psycopg2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

APP_TITLE = os.getenv("RO_DASH_TITLE", "custom-ai-bot (read-only)")

app = FastAPI(title=APP_TITLE)


def get_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


@app.get("/", response_class=HTMLResponse)
def index():
    # Very small read-only dashboard: latest updates + row counts.
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM health_daily")
    health_rows = cur.fetchone()[0]
    cur.execute("SELECT MAX(date) FROM health_daily")
    health_latest = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM exercise_activity")
    act_rows = cur.fetchone()[0]
    cur.execute("SELECT MAX(start_time) FROM exercise_activity")
    act_latest = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM training_plan_weekly")
    planw_rows = cur.fetchone()[0]
    cur.execute("SELECT MAX(week_start) FROM training_plan_weekly")
    planw_latest = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM training_plan_day")
    pland_rows = cur.fetchone()[0]
    cur.execute("SELECT MAX(plan_date) FROM training_plan_day")
    pland_latest = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM terminal_command_log")
    audit_rows = cur.fetchone()[0]
    cur.execute("SELECT MAX(ts) FROM terminal_command_log")
    audit_latest = cur.fetchone()[0]

    cur.close()
    conn.close()

    def fmt(x):
        return "-" if x is None else str(x)

    html = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{APP_TITLE}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .muted {{ color: #666; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 720px; margin-top: 16px; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
    th {{ background: #f7f7f7; }}
    code {{ background: #f2f2f2; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>{APP_TITLE}</h1>
  <div class=\"muted\">Read-only summary. Keep this localhost-only and access via SSH port-forward.</div>

  <table>
    <tr><th>Dataset</th><th>Rows</th><th>Latest</th></tr>
    <tr><td>health_daily</td><td>{health_rows}</td><td>{fmt(health_latest)}</td></tr>
    <tr><td>exercise_activity</td><td>{act_rows}</td><td>{fmt(act_latest)}</td></tr>
    <tr><td>training_plan_weekly</td><td>{planw_rows}</td><td>{fmt(planw_latest)}</td></tr>
    <tr><td>training_plan_day</td><td>{pland_rows}</td><td>{fmt(pland_latest)}</td></tr>
    <tr><td>terminal_command_log</td><td>{audit_rows}</td><td>{fmt(audit_latest)}</td></tr>
  </table>

  <p class=\"muted\">Health check: <code>/health</code></p>
</body>
</html>
"""
    return HTMLResponse(html)
