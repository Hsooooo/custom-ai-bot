# Deploying to VPS (Official Guide)

Since you have already installed `clawdbot` on your VPS and have Docker containers running, here is how to connect them.

## 1. Environment Verification

Ensure you are in the project root on your VPS:
```bash
cd ~/custom-ai-bot
```

Ensure your worker containers are running:
```bash
docker compose ps
# Expected output:
# custom-ai-bot-worker-garmin-1   Up
# custom-ai-bot-worker-brief-1    Up
# custom-ai-bot-postgres-1        Up
```
*(Note: Docker Compose v2 might use hyphens instead of underscores found in older versions. If your container names are different, check with `docker ps` and update `SKILL.md` accordingly.)*

## 2. Onboarding (Linking ClawdBot to this Folder)

Tell ClawdBot that **this directory** is your workspace.

```bash
clawdbot onboard
```
1.  **Select Workspace**: Choose "Current Directory" (`.`).
2.  **Confirm Skills**: It should detect `skills/health`, `skills/notes`, `skills/system`.

## 3. Using the Skills (TUI)

Now you can chat with the bot in your VPS terminal.

```bash
clawdbot tui
```

**Try these commands:**
- "서버 상태 보여줘" (Runs `skills/system/SKILL.md` -> `docker ps` on host)
- "어제 수면 어땠어?" (Runs `skills/health/SKILL.md` -> `docker exec ...`)

## 4. Troubleshooting Network

If the bot says "Cannot connect to database":
- The `SKILL.md` uses `docker exec custom-ai-bot-worker-brief-1 python ...`.
- This executes the script **INSIDE** the container, where it CAN talk to Postgres.
- **Do not** try to run the python script directly on the Ubuntu host (`python workers/.../query.py`) because the host likely doesn't have the `clawd_net` DNS resolution for `postgres`.

## 5. Running as a Background Service

Currently `clawdbot tui` is for interactive use. To keep the Gateway running after you log out:

```bash
clawdbot daemon start
```
(Or follow the `onboard` instructions to install the systemd service).
