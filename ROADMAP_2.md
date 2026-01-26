# Clawd Bot Migration Roadmap (Official Edition)

> **Decision**: Adopt the **Official ClawdBot CLI** directly instead of building a custom clone.
> **Reason**: Addresses all key gaps (LLM, OAuth, Real-time) natively without maintenance debt.

---

## 🚫 Changes from Previous Plans
- **Dropped**: Custom Python "Agent Core", "Intent Parser", "Router".
- **Dropped**: Google Vertex AI integration (Official bot handles OAuth).
- **New Focus**: Configuration & Skill Porting.

---

## Phase 3: Deployment & Migration

### 3.1 Prerequisite Check
- [ ] **Node.js Upgrade**: ClawdBot requires Node.js v22+. (Current System: v16.x)
  - Action: Update via `nvm` or `brew`.
- [ ] **Installation**:
  ```bash
  curl -fsSL https://clawd.bot/install.sh | bash
  clawdbot onboard --install-daemon
  ```

### 3.2 Authentication (Solved)
- **Desired Feature**: OAuth (No API Key).
- **Solution**: Run `clawdbot models auth login` (supports interactive browser login).

### 3.3 Skill Porting Strategy (The Real Work)
Instead of writing bot code, we write **Skill Definitions** that wrap our existing Python scripts.

#### A. Health Data (Garmin)
*Goal: Replace `/brief` command.*
1.  **Script**: Modify `workers/worker-brief/query.py` to accept CLI arguments (date, metrics) instead of hardcoded logic.
2.  **Skill**: `skills/health/SKILL.md`
    ```yaml
    name: health-stats
    description: Get health and sleep stats from Postgres database.
    triggers: ["sleep", "stress", "heart rate", "briefing"]
    ```
    *Instruction: "Run `python workers/worker-brief/query.py --date {date}` and summarize."*

#### B. Knowledge Base (Obsidian)
*Goal: Read/Write notes.*
1.  **Script**: Use existing logic from `worker-notes`.
2.  **Skill**: `skills/notes/SKILL.md`
    *Instruction: "To search notes, run `grep -r ...` in the vault dir."* (ClawdBot can run bash directly!).

#### C. System Control
*Goal: Monitor server.*
1.  **Skill**: `skills/system/SKILL.md`
    *Instruction: "Use `top` or `df -h` to check system status."*

---

## Phase 4: Expansion (Awesome Skills)

With the official bot, we can simply download community skills:
- **Git**: `clawdbot install git-agent` (conceptual) or copy from awesome-repo.
- **Web**: Native browser abilities are built-in.

---

## Immediate Next Steps
1.  **User Action**: Update Node.js to v22+.
2.  **Install**: Run ClawdBot installation.
3.  **Config**: Create `skills/` directory and move our logic there.
