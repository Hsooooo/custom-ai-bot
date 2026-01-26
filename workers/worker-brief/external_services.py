"""
External Service Integrations for Worker Brief
- Weather API (OpenWeatherMap)
- Google Calendar API
- GitHub API
"""

import os
import logging
import datetime
from typing import Optional, List, Dict
import httpx

logger = logging.getLogger('worker-brief.external')

# Environment Variables
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_CITY = os.getenv("OPENWEATHER_CITY", "Seoul")
OPENWEATHER_UNITS = os.getenv("OPENWEATHER_UNITS", "metric")

GOOGLE_CALENDAR_API_KEY = os.getenv("GOOGLE_CALENDAR_API_KEY")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")


# =============================================================================
# Weather API (OpenWeatherMap)
# =============================================================================

async def get_weather() -> Optional[Dict]:
    """
    Fetch current weather from OpenWeatherMap API.
    
    Returns:
        {
            'temp': 15.2,
            'feels_like': 14.0,
            'humidity': 65,
            'description': '맑음',
            'icon': '☀️',
            'wind_speed': 3.5,
            'temp_min': 12.0,
            'temp_max': 18.0
        }
    """
    if not OPENWEATHER_API_KEY:
        logger.warning("OPENWEATHER_API_KEY not configured")
        return None
    
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": OPENWEATHER_CITY,
            "appid": OPENWEATHER_API_KEY,
            "units": OPENWEATHER_UNITS,
            "lang": "kr"  # Korean descriptions
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Map weather condition to emoji
        weather_icons = {
            "01": "☀️",  # clear sky
            "02": "🌤️",  # few clouds
            "03": "☁️",  # scattered clouds
            "04": "☁️",  # broken clouds
            "09": "🌧️",  # shower rain
            "10": "🌧️",  # rain
            "11": "⛈️",  # thunderstorm
            "13": "❄️",  # snow
            "50": "🌫️",  # mist
        }
        
        icon_code = data["weather"][0]["icon"][:2]
        weather_emoji = weather_icons.get(icon_code, "🌡️")
        
        return {
            "temp": round(data["main"]["temp"], 1),
            "feels_like": round(data["main"]["feels_like"], 1),
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
            "icon": weather_emoji,
            "wind_speed": round(data["wind"]["speed"], 1),
            "temp_min": round(data["main"]["temp_min"], 1),
            "temp_max": round(data["main"]["temp_max"], 1),
            "city": data["name"]
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Weather API HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return None


def format_weather(weather: Optional[Dict]) -> str:
    """Format weather data for briefing message."""
    if not weather:
        return "🌡️ 날씨 정보 없음"
    
    lines = [
        f"{weather['icon']} *{weather['city']}*: {weather['description']}",
        f"  🌡️ 현재 {weather['temp']}°C (체감 {weather['feels_like']}°C)",
        f"  📊 최저 {weather['temp_min']}°C / 최고 {weather['temp_max']}°C",
        f"  💧 습도 {weather['humidity']}% | 💨 바람 {weather['wind_speed']}m/s"
    ]
    return "\n".join(lines)


# =============================================================================
# Google Calendar API
# =============================================================================

async def get_calendar_events(max_results: int = 5) -> List[Dict]:
    """
    Fetch today's events from Google Calendar.
    
    Note: For full OAuth2 flow, you'd need google-auth-oauthlib.
    This implementation uses a simple API key approach for public calendars,
    or expects a service account setup for private calendars.
    
    Returns:
        [
            {
                'summary': 'Meeting with Team',
                'start': '10:00',
                'end': '11:00',
                'location': 'Conference Room A',
                'all_day': False
            },
            ...
        ]
    """
    if not GOOGLE_CALENDAR_API_KEY or not GOOGLE_CALENDAR_ID:
        logger.warning("Google Calendar not configured")
        return []
    
    try:
        # Get today's time range
        today = datetime.date.today()
        time_min = datetime.datetime.combine(today, datetime.time.min).isoformat() + "Z"
        time_max = datetime.datetime.combine(today, datetime.time.max).isoformat() + "Z"
        
        url = f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events"
        params = {
            "key": GOOGLE_CALENDAR_API_KEY,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        events = []
        for item in data.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})
            
            # Check if all-day event
            all_day = "date" in start
            
            if all_day:
                start_str = "종일"
                end_str = ""
            else:
                start_dt = datetime.datetime.fromisoformat(start.get("dateTime", "").replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(end.get("dateTime", "").replace("Z", "+00:00"))
                start_str = start_dt.strftime("%H:%M")
                end_str = end_dt.strftime("%H:%M")
            
            events.append({
                "summary": item.get("summary", "제목 없음"),
                "start": start_str,
                "end": end_str,
                "location": item.get("location", ""),
                "all_day": all_day
            })
        
        return events
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Calendar API HTTP error: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Calendar API error: {e}")
        return []


def format_calendar_events(events: List[Dict]) -> str:
    """Format calendar events for briefing message."""
    if not events:
        return "📆 오늘 일정 없음"
    
    lines = ["📆 *오늘 일정*:"]
    for event in events:
        if event["all_day"]:
            time_str = "🗓️ 종일"
        else:
            time_str = f"⏰ {event['start']}-{event['end']}"
        
        location = f" 📍 {event['location']}" if event["location"] else ""
        lines.append(f"  {time_str} {event['summary']}{location}")
    
    return "\n".join(lines)


# =============================================================================
# GitHub API
# =============================================================================

async def get_github_activity() -> Dict:
    """
    Fetch recent GitHub activity for the user.
    
    Returns:
        {
            'commits_today': 5,
            'prs_open': 2,
            'prs_merged_today': 1,
            'issues_open': 3,
            'recent_repos': ['repo1', 'repo2']
        }
    """
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        logger.warning("GitHub not configured")
        return {}
    
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        today = datetime.date.today()
        since = datetime.datetime.combine(today, datetime.time.min).isoformat() + "Z"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get user's events (commits, PRs, etc.)
            events_url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"
            events_response = await client.get(events_url, headers=headers, params={"per_page": 30})
            events_response.raise_for_status()
            events = events_response.json()
            
            # Get open PRs created by user
            prs_url = f"https://api.github.com/search/issues"
            prs_params = {
                "q": f"author:{GITHUB_USERNAME} type:pr state:open",
                "per_page": 10
            }
            prs_response = await client.get(prs_url, headers=headers, params=prs_params)
            prs_data = prs_response.json() if prs_response.status_code == 200 else {"total_count": 0}
        
        # Count today's commits
        commits_today = 0
        repos_today = set()
        today_str = today.isoformat()
        
        for event in events:
            event_date = event.get("created_at", "")[:10]
            if event_date == today_str:
                if event["type"] == "PushEvent":
                    commits_today += len(event.get("payload", {}).get("commits", []))
                    repos_today.add(event.get("repo", {}).get("name", "").split("/")[-1])
        
        return {
            "commits_today": commits_today,
            "prs_open": prs_data.get("total_count", 0),
            "recent_repos": list(repos_today)[:3]
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"GitHub API HTTP error: {e.response.status_code}")
        return {}
    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return {}


def format_github_activity(activity: Dict) -> str:
    """Format GitHub activity for briefing message."""
    if not activity:
        return ""
    
    commits = activity.get("commits_today", 0)
    prs = activity.get("prs_open", 0)
    repos = activity.get("recent_repos", [])
    
    if commits == 0 and prs == 0:
        return ""
    
    lines = ["💻 *GitHub*:"]
    
    if commits > 0:
        repos_str = ", ".join(repos) if repos else ""
        lines.append(f"  📝 오늘 커밋: {commits}개" + (f" ({repos_str})" if repos_str else ""))
    
    if prs > 0:
        lines.append(f"  🔀 열린 PR: {prs}개")
    
    return "\n".join(lines)
