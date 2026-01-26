import pytest
import datetime


def test_health_markdown_format(sample_health_data):
    """Test health markdown generation format."""
    stats = sample_health_data
    date = stats['date']

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
"""

    assert "# Health Summary - 2026-01-26" in content
    assert "7.5 hours" in content
    assert "Score**: 85" in content
    assert "Max BB**: 92" in content
    assert "Resting HR**: 58" in content
    assert "HRV Status**: BALANCED" in content


def test_activity_markdown_format(sample_garmin_activity):
    """Test exercise activity markdown generation."""
    act = sample_garmin_activity

    activity_type = act['activityType']['typeKey']
    activity_name = act['activityName']
    distance_km = act['distance'] / 1000
    duration_sec = act['duration']
    duration_min = duration_sec // 60

    content = f"""# {activity_name} - 2026-01-26

## Summary
- **Type**: {activity_type}
- **Duration**: {duration_min}m
- **Distance**: {distance_km:.2f} km
- **Calories**: {act['calories']} kcal

## Heart Rate
- **Average HR**: {act['averageHR']} bpm
- **Max HR**: {act['maxHR']} bpm
"""

    assert "Morning Run" in content
    assert "running" in content
    assert "30m" in content
    assert "5.00 km" in content
    assert "350 kcal" in content
    assert "145 bpm" in content
    assert "165 bpm" in content


def test_format_duration():
    """Test duration formatting helper."""
    def format_duration(seconds):
        if not seconds:
            return "N/A"
        minutes = seconds // 60
        if minutes >= 60:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
        return f"{minutes}m"

    assert format_duration(1800) == "30m"  # 30 minutes
    assert format_duration(3600) == "1h 0m"  # 1 hour
    assert format_duration(5400) == "1h 30m"  # 1.5 hours
    assert format_duration(0) == "N/A"
    assert format_duration(None) == "N/A"


def test_briefing_message_format(sample_health_data):
    """Test morning briefing message format."""
    health = sample_health_data

    lines = ["🌅 *Good Morning!*\n"]
    lines.append(f"😴 *어제 수면*: {health['sleep_hours']}시간 (점수: {health['sleep_score']})")
    lines.append(f"🔋 *Body Battery*: {health['body_battery_max']}%")
    lines.append(f"💓 *안정시 심박수*: {health['resting_hr']} bpm")

    message = "\n".join(lines)

    assert "Good Morning" in message
    assert "7.5시간" in message
    assert "점수: 85" in message
    assert "92%" in message
    assert "58 bpm" in message
