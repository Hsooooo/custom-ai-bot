# gcal_cli.py

Minimal Google Calendar helper (Service Account).

## Install deps (once)

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

cd /home/ubuntu/clawd
python3 -m venv .venv
. .venv/bin/activate
pip install -U google-api-python-client google-auth google-auth-httplib2 python-dateutil
```

## Configure env

```bash
export GCAL_SA_JSON=/home/ubuntu/custom-ai-bot-1c5b8c569f56.json
export GCAL_CALENDAR_ID='...@group.calendar.google.com'
export TZ=Asia/Seoul
```

## Usage

List events (today):
```bash
python tools/gcal/gcal_cli.py list --days 1 --limit 10
```

Create event:
```bash
python tools/gcal/gcal_cli.py create --summary "치과" --when "내일 10:00" --duration-min 60
```

Delete event (by id):
```bash
python tools/gcal/gcal_cli.py delete --event-id <event_id>
```

Delete event (match by time + summary substring):
```bash
python tools/gcal/gcal_cli.py delete --when "내일 10:00" --summary-contains "치과" --days 7
```
