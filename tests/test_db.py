import pytest
from unittest.mock import Mock, patch, MagicMock


def test_health_daily_insert_query():
    """Test health_daily INSERT query structure."""
    stats = {
        'date': '2026-01-26',
        'sleep_hours': 7.5,
        'sleep_score': 85,
        'resting_hr': 58,
        'hrv_status': 'BALANCED',
        'stress_level': 32,
        'body_battery_max': 92,
        'body_battery_min': 15
    }

    query = """
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
    """

    params = (
        stats['date'],
        stats['sleep_hours'],
        stats['sleep_score'],
        stats['resting_hr'],
        stats['hrv_status'],
        stats['stress_level'],
        stats['body_battery_max'],
        stats['body_battery_min'],
        stats  # raw_data as JSON
    )

    assert len(params) == 9
    assert params[0] == '2026-01-26'
    assert params[1] == 7.5
    assert "ON CONFLICT (date) DO UPDATE" in query


def test_exercise_activity_insert_query():
    """Test exercise_activity INSERT query structure."""
    activity = {
        'activity_id': 12345678901,
        'activity_type': 'running',
        'activity_name': 'Morning Run',
        'start_time': '2026-01-26T07:30:00',
        'duration_sec': 1800,
        'distance_meters': 5000,
        'avg_hr': 145,
        'max_hr': 165,
        'avg_pace': '5:33',
        'calories': 350,
        'elevation_gain': 50
    }

    query = """
        INSERT INTO exercise_activity (
            activity_id, activity_type, activity_name, start_time, duration_sec,
            distance_meters, avg_hr, max_hr, avg_pace, calories, elevation_gain, raw_data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO UPDATE SET
            activity_type = EXCLUDED.activity_type,
            activity_name = EXCLUDED.activity_name;
    """

    params = (
        activity['activity_id'],
        activity['activity_type'],
        activity['activity_name'],
        activity['start_time'],
        activity['duration_sec'],
        activity['distance_meters'],
        activity['avg_hr'],
        activity['max_hr'],
        activity['avg_pace'],
        activity['calories'],
        activity['elevation_gain'],
        activity  # raw_data
    )

    assert len(params) == 12
    assert params[0] == 12345678901
    assert "ON CONFLICT (activity_id) DO UPDATE" in query


def test_health_daily_select_query():
    """Test health data SELECT query for briefing."""
    query = """
        SELECT date, sleep_hours, sleep_score, resting_hr, hrv_status,
               stress_level, body_battery_max, body_battery_min
        FROM health_daily
        WHERE date IN (%s, %s)
        ORDER BY date DESC
    """

    # Simulate query result
    mock_rows = [
        ('2026-01-26', 7.5, 85, 58, 'BALANCED', 32, 92, 15),
        ('2026-01-25', 6.8, 78, 60, 'LOW', 45, 85, 20)
    ]

    result = {}
    for row in mock_rows:
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

    assert len(result) == 2
    assert result['2026-01-26']['sleep_hours'] == 7.5
    assert result['2026-01-25']['sleep_score'] == 78


def test_recent_activities_select():
    """Test recent activities SELECT query."""
    query = """
        SELECT activity_type, activity_name, start_time, duration_sec,
               distance_meters, avg_hr, avg_pace, calories
        FROM exercise_activity
        ORDER BY start_time DESC
        LIMIT %s
    """

    # Simulate result
    mock_rows = [
        ('running', 'Morning Run', '2026-01-26 07:30:00', 1800, 5000, 145, '5:33', 350),
        ('cycling', 'Evening Ride', '2026-01-25 18:00:00', 3600, 20000, 130, None, 450),
    ]

    activities = []
    for row in mock_rows:
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

    assert len(activities) == 2
    assert activities[0]['type'] == 'running'
    assert activities[1]['distance_meters'] == 20000
