import pytest
import os
import sys
from unittest.mock import MagicMock

# Add workers to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workers', 'worker-garmin'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workers', 'worker-brief'))

# Try importing redis, but it's optional for tests
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


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


# Agent-related fixtures

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    if REDIS_AVAILABLE:
        mock_client = MagicMock(spec=redis.Redis)
    else:
        mock_client = MagicMock()
    mock_client.lrange.return_value = []
    mock_client.lpush.return_value = 1
    mock_client.ltrim.return_value = True
    mock_client.expire.return_value = True
    mock_client.delete.return_value = 1
    return mock_client


@pytest.fixture
def sample_skill_content():
    """Sample SKILL.md content for testing."""
    return '''---
name: test-skill
description: Test skill for unit tests
triggers:
  - "test"
  - "테스트"
---

## Instructions
This is a test skill.

## Examples
- "Run test"
- "테스트 실행"
'''


@pytest.fixture
def sample_tool_definition():
    """Sample tool definition for testing."""
    return {
        "name": "get_health_data",
        "description": "Get health data from database",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to retrieve"
                }
            },
            "required": []
        }
    }


@pytest.fixture
def sample_conversation_history():
    """Sample conversation history for testing."""
    return [
        {"role": "user", "content": "안녕", "timestamp": 1000.0},
        {"role": "assistant", "content": "안녕하세요!", "timestamp": 1001.0},
        {"role": "user", "content": "어제 수면 어땠어?", "timestamp": 1002.0}
    ]
