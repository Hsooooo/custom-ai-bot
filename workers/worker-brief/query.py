#!/usr/bin/env python3
"""CLI tool for querying health and exercise data.

This script is designed to be called by ClawdBot CLI.

Usage:
    python query.py health [--date YYYY-MM-DD] [--days N]
    python query.py exercise [--days N] [--limit N]
    python query.py briefing
"""

import os
import sys
import json
import argparse
import datetime
import psycopg2

# Database configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")


def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def query_health(date_str=None, days=1):
    """Query health data from database.

    Args:
        date_str: Target date (YYYY-MM-DD), defaults to today
        days: Number of days to query

    Returns:
        List of health records as dicts
    """
    conn = get_db_connection()
    cur = conn.cursor()

    if date_str:
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.date.today()

    start_date = target_date - datetime.timedelta(days=days-1)

    cur.execute("""
        SELECT date, sleep_hours, sleep_score, resting_hr, hrv_status,
               stress_level, body_battery_max, body_battery_min
        FROM health_daily
        WHERE date BETWEEN %s AND %s
        ORDER BY date DESC
    """, (start_date, target_date))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "date": str(row[0]),
            "sleep_hours": row[1],
            "sleep_score": row[2],
            "resting_hr": row[3],
            "hrv_status": row[4],
            "stress_level": row[5],
            "body_battery_max": row[6],
            "body_battery_min": row[7]
        })

    return results


def query_exercise(days=7, limit=10):
    """Query exercise activities from database.

    Args:
        days: Look back this many days
        limit: Maximum number of activities to return

    Returns:
        List of exercise records as dicts
    """
    conn = get_db_connection()
    cur = conn.cursor()

    start_date = datetime.date.today() - datetime.timedelta(days=days)

    cur.execute("""
        SELECT activity_type, activity_name, start_time, duration_sec,
               distance_meters, avg_hr, max_hr, avg_pace, calories
        FROM exercise_activity
        WHERE start_time >= %s
        ORDER BY start_time DESC
        LIMIT %s
    """, (start_date, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "type": row[0],
            "name": row[1],
            "start_time": str(row[2]) if row[2] else None,
            "duration_sec": row[3],
            "duration_min": round(row[3] / 60, 1) if row[3] else None,
            "distance_meters": row[4],
            "distance_km": round(row[4] / 1000, 2) if row[4] else None,
            "avg_hr": row[5],
            "max_hr": row[6],
            "avg_pace": row[7],
            "calories": row[8]
        })

    return results


def generate_briefing():
    """Generate a text briefing summary."""
    health = query_health(days=2)
    exercise = query_exercise(days=7, limit=3)

    lines = []

    # Health data
    if health:
        latest = health[0]
        lines.append(f"=== Health Data ({latest['date']}) ===")
        lines.append(f"Sleep: {latest['sleep_hours']}h (score: {latest['sleep_score']})")
        lines.append(f"Resting HR: {latest['resting_hr']} bpm")
        lines.append(f"HRV Status: {latest['hrv_status']}")
        lines.append(f"Stress Level: {latest['stress_level']}")
        lines.append(f"Body Battery: {latest['body_battery_min']} - {latest['body_battery_max']}%")
    else:
        lines.append("No health data available.")

    lines.append("")

    # Exercise data
    if exercise:
        lines.append("=== Recent Exercise ===")
        for ex in exercise:
            duration = f"{ex['duration_min']}min" if ex['duration_min'] else "N/A"
            distance = f"{ex['distance_km']}km" if ex['distance_km'] else ""
            lines.append(f"- {ex['name'] or ex['type']}: {duration} {distance}")
    else:
        lines.append("No recent exercise data.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query health and exercise data")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Health command
    health_parser = subparsers.add_parser("health", help="Query health data")
    health_parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    health_parser.add_argument("--days", type=int, default=1, help="Number of days")
    health_parser.add_argument("--format", choices=["json", "text"], default="json")

    # Exercise command
    exercise_parser = subparsers.add_parser("exercise", help="Query exercise data")
    exercise_parser.add_argument("--days", type=int, default=7, help="Look back days")
    exercise_parser.add_argument("--limit", type=int, default=10, help="Max results")
    exercise_parser.add_argument("--format", choices=["json", "text"], default="json")

    # Briefing command
    subparsers.add_parser("briefing", help="Generate text briefing")

    args = parser.parse_args()

    if args.command == "health":
        data = query_health(date_str=args.date, days=args.days)
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            for d in data:
                print(f"{d['date']}: Sleep {d['sleep_hours']}h, HR {d['resting_hr']}, Stress {d['stress_level']}")

    elif args.command == "exercise":
        data = query_exercise(days=args.days, limit=args.limit)
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            for ex in data:
                print(f"{ex['start_time']}: {ex['name']} - {ex['duration_min']}min")

    elif args.command == "briefing":
        print(generate_briefing())

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
