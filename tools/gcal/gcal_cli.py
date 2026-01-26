#!/usr/bin/env python3
"""Google Calendar utility (Service Account).

This is a small CLI helper intended to be called by Clawdbot workflows.
It supports listing, creating, and deleting events using a Service Account JSON key.

Dependencies (install once):
  sudo apt-get update
  sudo apt-get install -y python3-pip python3-venv
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U google-api-python-client google-auth google-auth-httplib2 python-dateutil

Config via env:
  GCAL_SA_JSON=/path/to/service-account.json
  GCAL_CALENDAR_ID=...@group.calendar.google.com
  TZ=Asia/Seoul

Examples:
  GCAL_SA_JSON=... GCAL_CALENDAR_ID=... \
    python tools/gcal/gcal_cli.py list --days 1

  GCAL_SA_JSON=... GCAL_CALENDAR_ID=... \
    python tools/gcal/gcal_cli.py create --summary "치과" --when "내일 10:00" --duration-min 60

  # delete by event id
  GCAL_SA_JSON=... GCAL_CALENDAR_ID=... \
    python tools/gcal/gcal_cli.py delete --event-id <id>

  # delete by matching (time window + summary keyword)
  GCAL_SA_JSON=... GCAL_CALENDAR_ID=... \
    python tools/gcal/gcal_cli.py delete --when "내일 10:00" --summary-contains "치과" --days 2
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Optional, Any


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        _die(f"Missing required env: {name}")
    return v


def _local_tz_name() -> str:
    return os.getenv("TZ", "Asia/Seoul")


def _parse_when_korean(s: str, tz: dt.tzinfo) -> dt.datetime:
    """Parse minimal Korean relative datetime strings.

    Supported patterns:
      - "오늘 10:00", "내일 9", "모레 18:30"
      - "2026-01-30 14:00"

    For anything else, we fall back to dateutil (if installed).
    """

    s = s.strip()
    now = dt.datetime.now(tz)

    rel_days = {
        "오늘": 0,
        "내일": 1,
        "모레": 2,
    }

    parts = s.split()
    if len(parts) == 2 and parts[0] in rel_days:
        day = (now.date() + dt.timedelta(days=rel_days[parts[0]]))
        hm = parts[1]
        if ":" in hm:
            hh, mm = hm.split(":", 1)
        else:
            hh, mm = hm, "00"
        return dt.datetime.combine(day, dt.time(int(hh), int(mm)), tz)

    # ISO-ish fallback
    try:
        # Accept "YYYY-MM-DD HH:MM" or "YYYY-MM-DDTHH:MM"
        norm = s.replace("T", " ")
        d, t = norm.split(" ", 1)
        year, month, day = map(int, d.split("-"))
        hh, mm = map(int, t.split(":", 1))
        return dt.datetime(year, month, day, hh, mm, tzinfo=tz)
    except Exception:
        pass

    try:
        from dateutil import parser as du_parser  # type: ignore

        guessed = du_parser.parse(s)
        if guessed.tzinfo is None:
            guessed = guessed.replace(tzinfo=tz)
        return guessed
    except Exception as e:
        _die(
            "Could not parse --when. Try formats like '내일 10:00' or '2026-01-30 14:00'. "
            f"(detail: {e})"
        )


def _build_service(sa_json_path: str):
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except Exception as e:
        _die(
            "Missing Google API deps. Install as:\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install -y python3-pip python3-venv\n"
            "  python3 -m venv .venv && . .venv/bin/activate\n"
            "  pip install -U google-api-python-client google-auth google-auth-httplib2 python-dateutil\n"
            f"(detail: {e})"
        )

    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_file(sa_json_path, scopes=scopes)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _get_tz():
    tz_name = _local_tz_name()
    try:
        from zoneinfo import ZoneInfo

        return tz_name, ZoneInfo(tz_name)
    except Exception:
        return tz_name, dt.timezone.utc


def _event_time_str(ev: dict) -> tuple[str, str]:
    start_obj = ev.get("start", {})
    end_obj = ev.get("end", {})
    start_s = start_obj.get("dateTime") or start_obj.get("date") or ""
    end_s = end_obj.get("dateTime") or end_obj.get("date") or ""
    return start_s, end_s


def _list_events(service: Any, cal_id: str, *, start: dt.datetime, end: dt.datetime, limit: int) -> list[dict]:
    out: list[dict] = []
    page_token = None

    while True:
        resp = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                maxResults=limit,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        items = resp.get("items", [])
        out.extend(items)
        page_token = resp.get("nextPageToken")
        if not page_token or len(out) >= limit:
            return out[:limit]


def cmd_list(args: argparse.Namespace) -> None:
    sa_json = _require_env("GCAL_SA_JSON")
    cal_id = _require_env("GCAL_CALENDAR_ID")

    tz_name, tz = _get_tz()

    service = _build_service(sa_json)

    now = dt.datetime.now(tz)
    start = dt.datetime.combine(now.date(), dt.time.min, tz)
    end = start + dt.timedelta(days=int(args.days))

    items = _list_events(service, cal_id, start=start, end=end, limit=int(args.limit))
    for ev in items:
        ev_id = ev.get("id", "")
        summary = ev.get("summary", "(no title)")
        start_s, end_s = _event_time_str(ev)
        print(f"- {start_s} ~ {end_s} | {summary} | id={ev_id}")


def cmd_create(args: argparse.Namespace) -> None:
    sa_json = _require_env("GCAL_SA_JSON")
    cal_id = _require_env("GCAL_CALENDAR_ID")

    tz_name, tz = _get_tz()

    start_dt = _parse_when_korean(args.when, tz)

    if args.end:
        end_dt = _parse_when_korean(args.end, tz)
    else:
        dur_min = int(args.duration_min)
        end_dt = start_dt + dt.timedelta(minutes=dur_min)

    body = {
        "summary": args.summary,
        "location": args.location or "",
        "description": args.description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz_name},
    }

    service = _build_service(sa_json)
    created = service.events().insert(calendarId=cal_id, body=body).execute()

    # Print both id and link for downstream tooling
    ev_id = created.get("id")
    link = created.get("htmlLink")
    if ev_id:
        print(f"id={ev_id}")
    if link:
        print(link)


def cmd_delete(args: argparse.Namespace) -> None:
    sa_json = _require_env("GCAL_SA_JSON")
    cal_id = _require_env("GCAL_CALENDAR_ID")

    tz_name, tz = _get_tz()
    service = _build_service(sa_json)

    # Fast path: delete by id
    if args.event_id:
        service.events().delete(calendarId=cal_id, eventId=args.event_id).execute()
        print(f"deleted id={args.event_id}")
        return

    # Otherwise: search in a time window and delete matching event
    if not args.when or not args.summary_contains:
        _die("delete requires --event-id or (--when and --summary-contains)")

    target_start = _parse_when_korean(args.when, tz)
    # search window: [start_of_today, today+days]
    now = dt.datetime.now(tz)
    start = dt.datetime.combine(now.date(), dt.time.min, tz)
    end = start + dt.timedelta(days=int(args.days))

    items = _list_events(service, cal_id, start=start, end=end, limit=int(args.limit))

    def matches(ev: dict) -> bool:
        summary = (ev.get("summary") or "").strip()
        if args.summary_contains not in summary:
            return False
        start_s, _ = _event_time_str(ev)
        if not start_s:
            return False
        try:
            # start_s is RFC3339
            ev_start = dt.datetime.fromisoformat(start_s.replace("Z", "+00:00"))
            if ev_start.tzinfo is None:
                ev_start = ev_start.replace(tzinfo=tz)
        except Exception:
            return False
        # strict match: same minute
        return abs(int((ev_start - target_start).total_seconds())) < 60

    candidates = [ev for ev in items if matches(ev)]
    if not candidates:
        _die("No matching event found to delete. Try widening --days or adjust --when.", 3)
    if len(candidates) > 1 and not args.force:
        _die(
            f"Multiple ({len(candidates)}) matching events found. Re-run with --force or delete by --event-id.",
            3,
        )

    ev = candidates[0]
    ev_id = ev.get("id")
    if not ev_id:
        _die("Matched event has no id; cannot delete.")

    service.events().delete(calendarId=cal_id, eventId=ev_id).execute()
    start_s, end_s = _event_time_str(ev)
    print(f"deleted id={ev_id}")
    print(f"- {start_s} ~ {end_s} | {ev.get('summary','')}")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--days", type=int, default=1)
    p_list.add_argument("--limit", type=int, default=10)
    p_list.set_defaults(fn=cmd_list)

    p_create = sub.add_parser("create")
    p_create.add_argument("--summary", required=True)
    p_create.add_argument("--when", required=True, help="e.g. '내일 10:00' or '2026-01-30 14:00'")
    p_create.add_argument("--duration-min", default=60)
    p_create.add_argument("--end", help="optional end datetime; overrides duration")
    p_create.add_argument("--location")
    p_create.add_argument("--description")
    p_create.set_defaults(fn=cmd_create)

    p_del = sub.add_parser("delete")
    p_del.add_argument("--event-id", help="delete by event id")
    p_del.add_argument("--when", help="match by start time (e.g. '내일 10:00')")
    p_del.add_argument("--summary-contains", help="substring match on summary")
    p_del.add_argument("--days", type=int, default=7, help="search window in days starting today")
    p_del.add_argument("--limit", type=int, default=50, help="max events to scan")
    p_del.add_argument("--force", action="store_true", help="allow delete when multiple matches")
    p_del.set_defaults(fn=cmd_delete)

    args = p.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
