# Clawd Bot 2.0 Usage Guide

Welcome to the **Clawd Bot 2.0**. This guide explains how to install, configure, and use your new AI-powered assistant.

## 🏗 Architecture Overview

| Component | Role | Changes |
|-----------|------|---------|
| **Core** | `clawdbot` CLI | Replaces custom Python bot. Handles natural language & tools. |
| **Brain** | LLM (Claude 3.5) | Connected via OAuth (no hardcoded keys). |
| **Skills** | `SKILL.md` | New bridge between AI and your existing Python workers. |
| **Data** | Custom Workers | `worker-garmin`, `worker-notes` run in background as usual. |

---

## 🚀 Installation & Setup

### 1. Prerequisite: Node.js v22+
ClawdBot requires a modern Node.js environment.

```bash
# Check current version
node -v

# Install/Update via nvm (Recommended)
nvm install 22
nvm use 22

# OR via Homebrew
brew install node
```

### 2. Install ClawdBot
Install the official CLI tool:

```bash
curl -fsSL https://clawd.bot/install.sh | bash
```

### 3. Initialize & Login
Authenticate using your existing Claude credentials (OAuth).

```bash
# 1. Initialize daemon
clawdbot onboard --install-daemon

# 2. Login (Opens browser window)
clawdbot models auth login
```

---

## 🧠 Configuration (Skills)

You have defined **3 Custom Skills** to leverage your existing data.
These are located in the `skills/` directory.

### 1. Health Skill (`skills/health`)
*   **Triggers**: "sleep", "heart rate", "briefing", "건강", "수면"
*   **Action**: Calls `worker-brief/query.py` to fetch data from Postgres.
*   **Usage**:
    > "어제 수면 어땠어?"
    > "지난주 운동 기록 요약해줘"

### 2. Notes Skill (`skills/notes`)
*   **Triggers**: "notes", "obsidian", "노트 search"
*   **Action**: Searches your Obsidian vault using `grep`.
*   **Usage**:
    > "Find notes about 'project idea'"
    > "Read today's daily note"

### 3. System Skill (`skills/system`)
*   **Triggers**: "status", "server", "docker"
*   **Action**: Checks VPS `top`, `df`, and Docker container status.
*   **Usage**:
    > "서버 상태 점검해줘"
    > "Check if the Postgres container is healthy"

---

## 🏃‍♂️ How to Run

### Interactive Mode (Terminal)
You can chat with the bot directly in your terminal:

```bash
clawdbot
# Bot: Hello! How can I help you?
# You: 어제 수면 어땠어?
```

### Telegram Integration
To allow Telegram access, you simply run `clawdbot` as a **Gateway** or use a bridge script that forwards messages to the `clawdbot` CLI.

*(Detailed Telegram bridge setup will be the next step in deployment if needed)*

---

## 🛠 Troubleshooting

**Q: The bot says it can't find the `query.py` script.**
A: Ensure you are running `clawdbot` from the project root (`/Users/ihansu/IdeaProjects/custom-ai-bot`) so relative paths in instructions resolve correctly.

**Q: OAuth login fails.**
A: Try running `clawdbot models auth logout` and logging in again. Ensure port 3000 is open if running on a remote server.

**Q: Node.js version error.**
A: Ensure `node -v` shows v22.0.0 or higher.
