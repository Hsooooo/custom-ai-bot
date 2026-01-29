"""
Worker Monitor - Container and System Health Monitoring

Features:
- Docker container health checks
- Disk and memory usage monitoring
- Alert notifications via Telegram
- Periodic health reports
"""

import os
import time
import logging
import datetime
import asyncio
import json
import schedule
import docker
from typing import Dict, List, Optional
from telegram import Bot

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('worker-monitor')

# Environment Variables
# Default alert channel: Telegram DM to admin via a dedicated bot token.
# If ALERT_TELEGRAM_BOT_TOKEN is set, it overrides TELEGRAM_BOT_TOKEN.
ALERT_TELEGRAM_BOT_TOKEN = os.getenv("ALERT_TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
TZ = os.getenv("TZ", "Asia/Seoul")

# Optional: Postgres for lightweight audit logs (TTL cleanup)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Monitoring thresholds
DISK_THRESHOLD_PERCENT = int(os.getenv("DISK_THRESHOLD_PERCENT", "85"))
MEMORY_THRESHOLD_PERCENT = int(os.getenv("MEMORY_THRESHOLD_PERCENT", "85"))
CONTAINER_RESTART_THRESHOLD = int(os.getenv("CONTAINER_RESTART_THRESHOLD", "3"))

# Alert cooldown (seconds) - don't spam alerts
ALERT_COOLDOWN = 3600  # 1 hour
last_alerts: Dict[str, float] = {}


def get_docker_client():
    """Get Docker client."""
    try:
        return docker.from_env()
    except docker.errors.DockerException as e:
        logger.error(f"Failed to connect to Docker: {e}")
        return None


async def send_telegram_alert(message: str, parse_mode: str = 'Markdown'):
    """Send alert via Telegram."""
    token = ALERT_TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN
    if not token or not TELEGRAM_ADMIN_ID:
        logger.warning("Telegram not configured")
        return

    try:
        bot = Bot(token=token)
        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_ID,
            text=message,
            parse_mode=parse_mode
        )
        logger.info("Alert sent successfully")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def should_send_alert(alert_key: str) -> bool:
    """Check if we should send an alert (cooldown check)."""
    now = time.time()
    last_time = last_alerts.get(alert_key, 0)
    
    if now - last_time >= ALERT_COOLDOWN:
        last_alerts[alert_key] = now
        return True
    return False


# =============================================================================
# Container Monitoring
# =============================================================================

def get_container_status() -> List[Dict]:
    """Get status of all containers."""
    client = get_docker_client()
    if not client:
        return []
    
    containers = []
    try:
        for container in client.containers.list(all=True):
            # Get container stats
            status = container.status
            name = container.name
            
            # Get restart count
            restart_count = container.attrs.get('RestartCount', 0)
            
            # Get health status if available
            health_status = None
            if 'Health' in container.attrs.get('State', {}):
                health_status = container.attrs['State']['Health'].get('Status')
            
            # Get uptime
            started_at = container.attrs.get('State', {}).get('StartedAt', '')
            
            containers.append({
                'name': name,
                'status': status,
                'health': health_status,
                'restart_count': restart_count,
                'started_at': started_at,
                'image': container.image.tags[0] if container.image.tags else 'unknown'
            })
            
    except Exception as e:
        logger.error(f"Error getting container status: {e}")
    
    return containers


def check_container_health() -> List[str]:
    """Check container health and return list of issues."""
    issues = []
    containers = get_container_status()
    
    for container in containers:
        name = container['name']
        
        # Check if container is stopped/exited
        if container['status'] in ['exited', 'dead']:
            issues.append(f"🔴 *{name}*: Container is {container['status']}")
        
        # Check for unhealthy containers
        elif container['health'] == 'unhealthy':
            issues.append(f"🟠 *{name}*: Container is unhealthy")
        
        # Check for excessive restarts
        elif container['restart_count'] >= CONTAINER_RESTART_THRESHOLD:
            issues.append(f"⚠️ *{name}*: Restarted {container['restart_count']} times")
    
    return issues


# =============================================================================
# System Resource Monitoring
# =============================================================================

def get_disk_usage() -> Dict:
    """Get disk usage information."""
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        
        return {
            'total_gb': round(total / (1024**3), 1),
            'used_gb': round(used / (1024**3), 1),
            'free_gb': round(free / (1024**3), 1),
            'percent_used': round((used / total) * 100, 1)
        }
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return {}


def get_memory_usage() -> Dict:
    """Get memory usage information."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]  # Get just the number
                    meminfo[key] = int(value)
        
        total_kb = meminfo.get('MemTotal', 0)
        available_kb = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
        used_kb = total_kb - available_kb
        
        return {
            'total_gb': round(total_kb / (1024**2), 1),
            'used_gb': round(used_kb / (1024**2), 1),
            'available_gb': round(available_kb / (1024**2), 1),
            'percent_used': round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting memory usage: {e}")
        return {}


def check_system_resources() -> List[str]:
    """Check system resources and return list of issues."""
    issues = []
    
    # Check disk usage
    disk = get_disk_usage()
    if disk and disk.get('percent_used', 0) >= DISK_THRESHOLD_PERCENT:
        issues.append(f"💾 *Disk*: {disk['percent_used']}% used ({disk['free_gb']}GB free)")
    
    # Check memory usage
    memory = get_memory_usage()
    if memory and memory.get('percent_used', 0) >= MEMORY_THRESHOLD_PERCENT:
        issues.append(f"🧠 *Memory*: {memory['percent_used']}% used ({memory['available_gb']}GB available)")
    
    return issues


# =============================================================================
# Health Report
# =============================================================================

def generate_health_report() -> str:
    """Generate comprehensive health report."""
    lines = ["📊 *System Health Report*\n"]
    lines.append(f"🕐 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Container status
    lines.append("*🐳 Containers:*")
    containers = get_container_status()
    
    if containers:
        for c in containers:
            status_emoji = {
                'running': '🟢',
                'exited': '🔴',
                'paused': '🟡',
                'restarting': '🟠',
                'dead': '💀'
            }.get(c['status'], '⚪')
            
            health_str = f" ({c['health']})" if c['health'] else ""
            restart_str = f" [↻{c['restart_count']}]" if c['restart_count'] > 0 else ""
            
            lines.append(f"  {status_emoji} {c['name']}{health_str}{restart_str}")
    else:
        lines.append("  ⚠️ Unable to get container status")
    
    lines.append("")
    
    # System resources
    lines.append("*💻 System Resources:*")
    
    disk = get_disk_usage()
    if disk:
        disk_emoji = "🟢" if disk['percent_used'] < 70 else "🟡" if disk['percent_used'] < 85 else "🔴"
        lines.append(f"  💾 Disk: {disk_emoji} {disk['percent_used']}% ({disk['free_gb']}GB free)")
    
    memory = get_memory_usage()
    if memory:
        mem_emoji = "🟢" if memory['percent_used'] < 70 else "🟡" if memory['percent_used'] < 85 else "🔴"
        lines.append(f"  🧠 Memory: {mem_emoji} {memory['percent_used']}% ({memory['available_gb']}GB available)")
    
    return "\n".join(lines)


# =============================================================================
# Lightweight Audit Log (Postgres)
# =============================================================================


def get_db_connection():
    try:
        import psycopg2
        return psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
    except Exception as e:
        logger.warning(f"DB connection unavailable: {e}")
        return None


def init_audit_db():
    """Create a small table for terminal command logs (TTL 7 days)."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS terminal_command_log (
          id BIGSERIAL PRIMARY KEY,
          ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          command TEXT NOT NULL,
          cwd TEXT,
          exit_code INTEGER,
          duration_ms INTEGER,
          raw JSONB
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def cleanup_audit_db(days: int = 7):
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("DELETE FROM terminal_command_log WHERE ts < NOW() - (%s || ' days')::interval", (str(days),))
    conn.commit()
    cur.close()
    conn.close()


# =============================================================================
# Docker Log Watcher (Garmin/Coach)
# =============================================================================

LOG_WATCH_CONTAINERS = os.getenv(
    "LOG_WATCH_CONTAINERS",
    "custom-ai-bot-worker-garmin-1,custom-ai-bot-worker-coach-1",
)
LOG_WATCH_CONTAINERS = [c.strip() for c in LOG_WATCH_CONTAINERS.split(",") if c.strip()]
LOG_WATCH_TAIL = int(os.getenv("LOG_WATCH_TAIL", "200"))
LOG_WATCH_POLL_SEC = int(os.getenv("LOG_WATCH_POLL_SEC", "60"))
LOG_WATCH_COOLDOWN_SEC = int(os.getenv("LOG_WATCH_COOLDOWN_SEC", "600"))

# simple per-container cooldown
_last_log_alert_at: Dict[str, float] = {}
_last_seen: Dict[str, int] = {}  # unix seconds

# very simple patterns; tune over time
SUSPECT_PATTERNS = [
    "Traceback",
    "ERROR",
    "CRITICAL",
    "FATAL",
    "Exception",
    "Failed to sync",
    "Critical sync error",
    "Garmin login failed",
    "Session invalid",
]


def _should_log_alert(key: str) -> bool:
    now = time.time()
    last = _last_log_alert_at.get(key, 0)
    if now - last >= LOG_WATCH_COOLDOWN_SEC:
        _last_log_alert_at[key] = now
        return True
    return False


def scan_container_logs_once():
    client = get_docker_client()
    if not client:
        return

    for name in LOG_WATCH_CONTAINERS:
        try:
            container = client.containers.get(name)
        except Exception:
            continue

        since = _last_seen.get(name)
        if not since:
            since = int(time.time()) - 300

        try:
            out = container.logs(since=since, tail=LOG_WATCH_TAIL)
            _last_seen[name] = int(time.time())
        except Exception as e:
            logger.warning(f"Failed reading logs for {name}: {e}")
            continue

        text = out.decode("utf-8", errors="ignore") if isinstance(out, (bytes, bytearray)) else str(out)
        if not text.strip():
            continue

        hit_lines = []
        for line in text.splitlines()[-LOG_WATCH_TAIL:]:
            if any(p in line for p in SUSPECT_PATTERNS):
                hit_lines.append(line)

        if not hit_lines:
            continue

        key = f"log:{name}"
        if not _should_log_alert(key):
            continue

        # include a small context window: last 15 lines
        last_lines = text.splitlines()[-15:]
        msg = "\n".join(last_lines)
        alert = (
            f"⚠️ *Log Alert*\n\n"
            f"*container*: `{name}`\n"
            f"*matched*: {len(hit_lines)} line(s)\n\n"
            f"```\n{msg[-3500:]}\n```"
        )
        try:
            asyncio.run(send_telegram_alert(alert, parse_mode="Markdown"))
        except Exception as e:
            logger.error(f"Failed sending log alert for {name}: {e}")


def sync_log_watch():
    scan_container_logs_once()


# =============================================================================
# Monitoring Loop
# =============================================================================

async def run_health_check():
    """Run health check and send alerts if needed."""
    logger.info("Running health check...")
    
    all_issues = []
    
    # Check containers
    container_issues = check_container_health()
    all_issues.extend(container_issues)
    
    # Check system resources
    resource_issues = check_system_resources()
    all_issues.extend(resource_issues)
    
    # Send alerts for issues
    if all_issues:
        # Group issues by type for cooldown
        for issue in all_issues:
            alert_key = issue.split(':')[0]  # Use the prefix as key
            
            if should_send_alert(alert_key):
                message = f"⚠️ *Alert*\n\n{issue}"
                await send_telegram_alert(message)
                logger.warning(f"Alert: {issue}")
    else:
        logger.info("Health check passed - no issues found")


async def run_health_report():
    """Send health report via Telegram."""
    report = generate_health_report()
    await send_telegram_alert(report)
    logger.info("Health report sent")


def sync_health_check():
    """Sync wrapper for health check."""
    asyncio.run(run_health_check())


def sync_health_report():
    """Sync wrapper for health report."""
    asyncio.run(run_health_report())


def main():
    logger.info("Worker Monitor started.")

    # Wait for dependencies to be available
    time.sleep(10)

    # Init DB table (best-effort)
    init_audit_db()

    # Test Docker connection
    client = get_docker_client()
    if client:
        logger.info("Docker connection successful")
        containers = client.containers.list()
        logger.info(f"Found {len(containers)} running containers")
    else:
        logger.error("Failed to connect to Docker")

    # Schedule health checks every 5 minutes
    schedule.every(5).minutes.do(sync_health_check)

    # Log watch (garmin/coach)
    schedule.every(LOG_WATCH_POLL_SEC).seconds.do(sync_log_watch)

    # Audit log cleanup (TTL 7 days)
    schedule.every().day.at("03:30").do(lambda: cleanup_audit_db(days=7))

    # Schedule daily health report at 09:00
    schedule.every().day.at("09:00").do(sync_health_report)

    # Schedule weekly detailed report on Monday at 09:00
    schedule.every().monday.at("09:00").do(sync_health_report)

    logger.info(
        "Scheduled: health check 5m; log watch {}s; daily report 09:00; audit cleanup 03:30".format(
            LOG_WATCH_POLL_SEC
        )
    )

    # Run initial health check + log watch once
    logger.info("Running initial health check...")
    sync_health_check()
    sync_log_watch()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
