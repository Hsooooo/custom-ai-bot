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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
TZ = os.getenv("TZ", "Asia/Seoul")

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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        logger.warning("Telegram not configured")
        return
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
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
    
    # Wait for Docker to be available
    time.sleep(10)
    
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
    
    # Schedule daily health report at 09:00
    schedule.every().day.at("09:00").do(sync_health_report)
    
    # Schedule weekly detailed report on Monday at 09:00
    schedule.every().monday.at("09:00").do(sync_health_report)
    
    logger.info("Scheduled: Health check every 5 min, Daily report at 09:00")
    
    # Run initial health check
    logger.info("Running initial health check...")
    sync_health_check()
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
