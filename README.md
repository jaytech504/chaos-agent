# Chaos Agent 🔥

> Autonomous API failure injection, gap analysis, and error handling code generator.
> Points at any running app, breaks it in 18 ways, finds every gap, writes the fixes,
> and opens GitHub Pull Requests — automatically.

Built for **Global AI Hackathon Series with Qwen Cloud** (Track 4: Autopilot Agent + Track 3: Agent Society)

---

## What It Does

```
You provide:  http://your-app.com  +  github.com/you/your-repo

Agent 1 — Discovery    Maps every API endpoint automatically
Agent 2 — Chaos        Injects 18 failure modes against each endpoint
Agent 3 — Observer     Watches and classifies each response
Agent 4 — Analyst      Finds patterns, calculates risk score 0-100
Agent 5 — Fix          Writes production-ready error handling code
Agent 6 — GitHub       Opens Pull Requests with the fixes applied
```

---

## Quick Start

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Create the database

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE chaos_agent;"
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
QWEN_API_KEY=sk-your-key-here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chaos_agent

# Optional — enables GitHub PR creation
GITHUB_TOKEN=ghp_your_token_here
```

### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Run the demo

```bash
# Without GitHub PRs
python run_demo.py

# With GitHub PRs (opens real PRs on your repo)
python run_demo.py your-username/your-repo
```

---

## Getting Your GitHub Token

1. Go to **https://github.com/settings/tokens**
2. Click **Generate new token (classic)**
3. Give it a name: `chaos-agent`
4. Select scopes:
   - ✅ `repo` (full repository access — needed to push branches and open PRs)
5. Click **Generate token**
6. Copy the token and paste it into your `.env` as `GITHUB_TOKEN`

---

## How GitHub Integration Works

When you provide a GitHub repo URL, after finding and generating fixes the GitHub Agent:

1. **Clones** your repo to a temp directory
2. **Reads** your source files to find the exact functions that need fixing
3. **Applies** the fix code to the correct location in the file
4. **Creates** a new branch: `chaos-agent/fix-name-{session-id}`
5. **Commits** with message: `fix: Add timeout handling for Stripe API calls`
6. **Opens a PR** with full description explaining what was found and why the fix works
7. **Updates status** when you merge (via webhook or manual sync)

One PR per critical finding. You review and merge each independently.

---

## Setting Up the GitHub Webhook (Optional)

To get real-time PR merge notifications in the dashboard:

1. Go to your repo → **Settings → Webhooks → Add webhook**
2. Payload URL: `https://your-server.com/api/github/webhook`
3. Content type: `application/json`
4. Events: select **Pull requests**
5. Click **Add webhook**

Without the webhook, you can manually sync PR status via:
```
POST /api/github/{pr_id}/sync
```

---

## API Reference

```
POST /api/sessions              Start a chaos session
GET  /api/sessions              List all sessions
GET  /api/sessions/{id}         Get session detail + failures + PRs
GET  /api/reports/{id}          Get full report with fixes
GET  /api/github                List all PRs
POST /api/github/webhook        GitHub webhook receiver
POST /api/github/{id}/sync      Manually sync PR status
WS   /ws/{session_id}           Live agent trace stream
```

---

## Failure Modes (18 Total)

| Category | Modes |
|---|---|
| Network | http_timeout, connection_refused, dns_failure, slow_response, connection_reset |
| Dependency | http_500, http_429, http_503, http_401, http_404 |
| Data | malformed_json, empty_response, wrong_content_type, partial_response, null_fields |
| Resource | db_connection_drop, db_timeout, db_constraint_violation |

---

## Stack

| Layer | Tech |
|---|---|
| AI | Qwen-Plus via Qwen Cloud API |
| Backend | FastAPI + Python |
| Database | PostgreSQL (asyncpg + SQLAlchemy) |
| Real-time | WebSockets |
| GitHub | PyGithub + GitPython |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Deployment | Alibaba Cloud ECS |

---

## License

MIT
