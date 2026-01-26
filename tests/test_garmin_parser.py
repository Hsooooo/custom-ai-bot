import pytest


def test_format_pace():
    """Test pace formatting from speed."""
    # Import the function (would need to be extracted to a utils module)
    def format_pace(speed_mps):
        if not speed_mps or speed_mps <= 0:
            return None
        pace_sec_per_km = 1000 / speed_mps
        minutes = int(pace_sec_per_km // 60)
        seconds = int(pace_sec_per_km % 60)
        return f"{minutes}:{seconds:02d}"

    # Test cases
    assert format_pace(3.0) == "5:33"  # ~5:33/km pace
    assert format_pace(2.5) == "6:40"  # ~6:40/km pace
    assert format_pace(4.0) == "4:10"  # ~4:10/km pace
    assert format_pace(0) is None
    assert format_pace(None) is None
    assert format_pace(-1) is None


def test_parse_activity(sample_garmin_activity):
    """Test parsing Garmin activity data."""
    act = sample_garmin_activity

    # Extract activity data (same logic as in worker-garmin)
    activity_data = {
        'activity_id': act.get('activityId'),
        'activity_type': act.get('activityType', {}).get('typeKey', 'unknown'),
        'activity_name': act.get('activityName', ''),
        'start_time': act.get('startTimeLocal'),
        'duration_sec': int(act.get('duration', 0)),
        'distance_meters': act.get('distance'),
        'avg_hr': act.get('averageHR'),
        'max_hr': act.get('maxHR'),
        'calories': act.get('calories'),
        'elevation_gain': act.get('elevationGain'),
    }

    assert activity_data['activity_id'] == 12345678901
    assert activity_data['activity_type'] == 'running'
    assert activity_data['activity_name'] == 'Morning Run'
    assert activity_data['duration_sec'] == 1800
    assert activity_data['distance_meters'] == 5000
    assert activity_data['avg_hr'] == 145
    assert activity_data['max_hr'] == 165
    assert activity_data['calories'] == 350


def test_parse_sleep_data(sample_sleep_data):
    """Test parsing sleep data from Garmin response."""
    sleep_data = sample_sleep_data

    sleep_seconds = sleep_data.get('dailySleepDto', {}).get('sleepTimeSeconds', 0)
    sleep_hours = round(sleep_seconds / 3600, 1)
    sleep_score = sleep_data.get('dailySleepDto', {}).get('sleepScoreValue', 0)

    assert sleep_hours == 7.5
    assert sleep_score == 85


def test_parse_body_battery(sample_user_summary):
    """Test extracting body battery min/max from array."""
    summary = sample_user_summary

    bb_values = [item[1] for item in summary['bodyBatteryValuesArray'] if item[1] is not None]

    assert len(bb_values) == 3
    assert max(bb_values) == 92
    assert min(bb_values) == 15


def test_parse_user_summary(sample_user_summary):
    """Test parsing user summary for health stats."""
    summary = sample_user_summary

    stats = {
        'resting_hr': summary.get('restingHeartRate', 0),
        'stress_level': summary.get('averageStressLevel', 0),
        'body_battery_max': summary.get('bodyBatteryMostRecentValue', 0),
    }

    assert stats['resting_hr'] == 58
    assert stats['stress_level'] == 32
    assert stats['body_battery_max'] == 92


def test_empty_activity_handling():
    """Test handling of empty or malformed activity data."""
    empty_activity = {}

    activity_data = {
        'activity_id': empty_activity.get('activityId'),
        'activity_type': empty_activity.get('activityType', {}).get('typeKey', 'unknown'),
        'activity_name': empty_activity.get('activityName', ''),
        'duration_sec': int(empty_activity.get('duration', 0)),
    }

    assert activity_data['activity_id'] is None
    assert activity_data['activity_type'] == 'unknown'
    assert activity_data['activity_name'] == ''
    assert activity_data['duration_sec'] == 0
