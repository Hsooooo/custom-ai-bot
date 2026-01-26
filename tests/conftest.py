import pytest
import os
import sys

# Add workers to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workers', 'worker-garmin'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workers', 'worker-brief'))


@pytest.fixture
def sample_garmin_activity():
    """Sample Garmin activity data for testing."""
    return {
        'activityId': 12345678901,
        'activityName': 'Morning Run',
        'activityType': {'typeKey': 'running'},
        'startTimeLocal': '2026-01-26T07:30:00',
        'duration': 1800,  # 30 minutes
        'distance': 5000,  # 5km
        'averageHR': 145,
        'maxHR': 165,
        'averageSpeed': 3.0,  # m/s
        'calories': 350,
        'elevationGain': 50
    }


@pytest.fixture
def sample_health_data():
    """Sample health daily data for testing."""
    return {
        'date': '2026-01-26',
        'sleep_hours': 7.5,
        'sleep_score': 85,
        'resting_hr': 58,
        'hrv_status': 'BALANCED',
        'stress_level': 32,
        'body_battery_max': 92,
        'body_battery_min': 15
    }


@pytest.fixture
def sample_sleep_data():
    """Sample Garmin sleep data response."""
    return {
        'dailySleepDto': {
            'sleepTimeSeconds': 27000,  # 7.5 hours
            'sleepScoreValue': 85
        }
    }


@pytest.fixture
def sample_user_summary():
    """Sample Garmin user summary response."""
    return {
        'restingHeartRate': 58,
        'averageStressLevel': 32,
        'bodyBatteryMostRecentValue': 92,
        'bodyBatteryValuesArray': [
            [1706234400000, 15],
            [1706238000000, 45],
            [1706241600000, 92]
        ]
    }
