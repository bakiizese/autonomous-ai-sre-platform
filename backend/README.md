# ⚙️ Autonomous AI SRE — Backend Service

The backend engine for the Autonomous AI SRE Platform. It watches GitHub repos for new issues, diagnoses them with a LangGraph agent graph backed by Gemini, verifies a generated fix in an isolated sandbox, and then **waits for a human to approve it** before opening a pull request. High-risk diagnoses email the people watching that repo.

Nothing merges without a human, and nothing is even written to GitHub without one: the pipeline stops at "awaiting approval," and it never approves or merges its own work.

---

## How it actually works

```text
GitHub issue created on a sandbox repo
        │
        ▼
Background poller (every 30s, or on demand via POST /api/poll/trigger-now)
detects it — poller state lives in Postgres, so it survives restarts
        │
        ▼
LangGraph agent graph
  diagnose ─▶ fix ─▶ test_gen ─▶ verify (sandboxed pytest)
     │                              │ failed and retries left?
     │                              └──────────▶ back to fix (with the failure output)
     │
     └─ inspected (read-only) repos stop here → status "diagnosed"
        │
        ▼
Run saved to Postgres, status "awaiting_approval" (or "verify_failed")
        │
        ├─ risk score above the threshold → email everyone subscribed to the repo
        ▼
A human reviews the diff, test and sandbox output in the dashboard
        │
   ┌────┴─────┐
   ▼          ▼
 approve    reject
   │
   ▼
POST /api/remediation-runs/{id}/approve — the only code path that writes to GitHub:
  • creates a branch
  • commits the fix + the test file
  • opens a pull request
  • comments on and closes the original issue
```

### Sandbox repos vs. inspected repos

| | Sandbox | Inspected |
|---|---|---|
| How it's created | Listed in `SANDBOX_REPOS`, seeded at startup | A visitor connects any **public** repo via `POST /api/repos/connect` |
| Auto-polled | Yes | No — refresh on demand only |
| Pipeline | Full graph, stops at `awaiting_approval` | Stops after `diagnose` (`diagnosed`) |
| Can be written to | Yes, after approval | Never |

`repo_type` is only ever set server-side: the public connect endpoint hardcodes `inspected`, so no request can promote a repo to writable. Private repos are rejected.

Existing open issues are ingested as a **baseline** when a repo is connected. They show up in the dashboard and can be triaged individually, but are never remediated in bulk — that protects the free-tier Gemini quota.

---

## Tech stack

| Layer | What it uses |
|---|---|
| API framework | FastAPI on Python 3.12, served by Uvicorn |
| Agent orchestration | LangGraph — diagnose/fix/test/verify nodes, conditional retry edge, per-node `RetryPolicy` |
| LLM | `google-genai` SDK, one narrow structured-output schema per node (model set by `GEMINI_MODEL_ID`) |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic migrations |
| Sandbox | `tempfile.TemporaryDirectory` + `subprocess` running `pytest`, with a timeout |
| GitHub integration | `httpx` against the GitHub REST API; every call goes through one method that records rate-limit headers |
| Email alerts | `smtplib` over SMTP (Gmail requires an **App Password** — see below) |
| Background jobs | An `asyncio` task started in the FastAPI `lifespan` |

---

## Directory structure

```text
backend/
├── app/
│   ├── api/                    # routers
│   │   ├── routes_repos.py         # connect / list / refresh
│   │   ├── routes_issues.py        # issues, source context, manual triage
│   │   ├── routes_remediation.py   # runs, approve, reject
│   │   ├── routes_demo.py          # sandbox "inject a bug"
│   │   ├── routes_poll.py          # trigger-now, status
│   │   ├── routes_subscribers.py   # email subscribe / unsubscribe
│   │   └── routes_status.py        # rate-limit status
│   ├── core/config.py          # pydantic-settings — all env vars load here
│   ├── db/                     # SQLAlchemy base, session, models
│   ├── schemas/                # agent.py (LLM output schemas), api.py (request/response models)
│   └── services/
│       ├── agent_engine.py         # the LangGraph pipeline
│       ├── remediation_service.py  # runs the pipeline, persists it, approve/reject
│       ├── repo_service.py         # connect repos, baseline/refresh issue ingestion
│       ├── poller_service.py       # poll loop + on-demand trigger
│       ├── notification_service.py # subscribers and risk-threshold alerts
│       ├── rate_limit_service.py   # Gemini/GitHub rate-limit state
│       ├── source_context_service.py # find the source file an issue talks about
│       ├── github_client.py        # all GitHub REST calls (repo-agnostic)
│       ├── sandbox_runner.py       # isolated pytest execution
│       ├── email_service.py        # SMTP sender
│       └── demo_scenarios.py       # canned bugs for the inject-a-bug demo
├── alembic/                    # migrations (0001_initial_schema)
├── main.py                     # app wiring, CORS, lifespan
├── Dockerfile / docker-entrypoint.sh
├── requirements.txt            # runtime (includes pytest — the sandbox shells out to it)
├── requirements-dev.txt        # test tooling
└── tests/                      # unit + integration
```

---

## Getting started

### 1. Prerequisites

- Python 3.12
- PostgreSQL (`docker compose up -d postgres` from the repo root gives you one on port 5433)
- A GitHub Personal Access Token with `repo` scope
- A Google AI Studio API key
- (Optional, for alerts) an SMTP account — see the Gmail note below

### 2. Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. Configure `.env`

**Create this file inside `backend/`, not the repo root** — `pydantic-settings` resolves `.env` relative to your current working directory when you launch the server, so if you `uvicorn` from the wrong folder these values silently fail to load.

```env
# Required
GEMINI_API_KEY=your_google_ai_studio_api_key

# GitHub — one platform token is used for every repo
GITHUB_TOKEN=ghp_your_personal_access_token
# Repos the platform may WRITE to (comma-separated). Anything else a visitor
# connects is read-only inspection.
SANDBOX_REPOS=bakiizese/sentinel-sre-playground

# Optional (defaults shown)
GEMINI_MODEL_ID=gemini-2.5-flash
DATABASE_URL=postgresql+psycopg://sre:sre@localhost:5433/sre
PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
POLL_INTERVAL_SECONDS=30
CRITICAL_RISK_THRESHOLD=8      # alert when risk score is strictly above this
AGENT_MAX_FIX_RETRIES=1        # extra fix attempts after a failed verification (0 disables)

# Public-demo abuse protection (0 disables a limit)
RATE_LIMIT_COSTLY_PER_10MIN=6  # per visitor: inject / triage / scratchpad / verify
RATE_LIMIT_LIGHT_PER_10MIN=30  # per visitor: connect / refresh / subscribe / context
DAILY_RUN_CAP=50               # total pipeline runs per rolling 24h, from any source

# Alert emails are always sent from this account (skipped silently if SMTP_HOST is unset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password    # no spaces — see note below
ALERT_EMAIL_FROM=your_email@gmail.com      # defaults to SMTP_USER if omitted
ADMIN_ALERT_EMAIL=you@example.com          # always alerted, for every repo
```

`GITHUB_REPO` and `ALERT_EMAIL_TO` from earlier versions still work: they're treated as `SANDBOX_REPOS` and `ADMIN_ALERT_EMAIL` when the new names aren't set.

> **Gmail specifically:** you cannot use your normal account password here — Gmail rejects it with a `535 Username and Password not accepted` error. Enable 2-Step Verification, then generate an [App Password](https://myaccount.google.com/apppasswords) and paste that in instead, with the spaces removed.

### 4. Migrate and run

```bash
alembic upgrade head
uvicorn main:app --reload --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- Watch for `🚀 Started background sandbox-repo poller` to confirm the poller is alive.
- `GET /` reports database connectivity, and is what the Docker healthcheck uses.

The Docker image runs `alembic upgrade head` itself on every start (see `docker-entrypoint.sh`).

---

## API routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check (includes a database ping) |
| POST | `/api/repos/connect` | Connect a public repo for read-only inspection; imports its open issues as a baseline |
| GET | `/api/repos` · `/api/repos/{id}` | List / fetch connected repos |
| POST | `/api/repos/{id}/refresh-issues` | Re-scan open issues; never triggers a fix |
| GET | `/api/repos/{id}/issues?scope=baseline\|live\|all` | Issues with their latest run status and risk |
| GET | `/api/repos/{id}/issues/{n}/context` | Best-effort resolution of the source file an issue mentions |
| POST | `/api/repos/{id}/issues/{n}/triage` | Run the pipeline on one issue |
| POST | `/api/repos/{id}/demo/inject-bug` | Sandbox only (403 otherwise): open a canned bug issue and run the pipeline on it |
| GET | `/api/remediation-runs/{id}` | One run: diagnosis, diff, test, sandbox output, graph trace |
| GET | `/api/repos/{id}/remediation-runs?status=` | Runs for a repo, e.g. `awaiting_approval` |
| POST | `/api/remediation-runs/{id}/approve` | Human approval — the only route that writes to GitHub |
| POST | `/api/remediation-runs/{id}/reject` | Reject a proposed fix; no GitHub writes |
| POST | `/api/poll/trigger-now` | Ask the poll loop to run immediately (returns 202) |
| GET | `/api/poll/status` | Last poll run and the configured interval |
| POST | `/api/repos/{id}/subscribe` | `{ "email": ... }` — get critical-risk alerts for a repo |
| GET | `/api/unsubscribe/{token}` | One-click unsubscribe (linked from alerts) |
| GET | `/api/status/rate-limits` | Gemini and GitHub rate-limit state |
| POST | `/api/triage` | Ad hoc: run the graph on pasted text; unpersisted, touches no repo |
| POST | `/api/verify` | Ad hoc: sandbox-verify pasted code and tests |
| POST | `/api/webhook/github` | Placeholder — detection is poller-driven; signed webhooks are a V2 item |

---

## Running this in public

Anyone can hit the demo, and part of what it runs is model-written code, so a few protections are on by default:

- **Sandbox:** generated tests run with a scrubbed environment (no `GITHUB_TOKEN`, `GEMINI_API_KEY` or SMTP password), CPU/memory/file-size limits, and — when the server runs as root, as in Docker — as the unprivileged `nobody` user, which also stops them reading the server's `/proc` environment. This is process-level isolation, **not** a container: it does not block network access. Stronger isolation (gVisor, Firecracker) is a V2 item.
- **Per-visitor limits:** costly actions (which spend Gemini quota or run the sandbox) and lighter GitHub-calling ones each have a per-IP limit per 10 minutes. Counters are in process memory, which is fine for a single instance. Run uvicorn with `--proxy-headers` behind a proxy so the real visitor IP is used (the Docker entrypoint does).
- **Daily cap:** `DAILY_RUN_CAP` bounds total pipeline runs per rolling 24h from any source, including strangers opening issues on a public sandbox repo. When it's hit, runs fail with a clear message and the inject button returns 429 without creating a GitHub issue.

---

## Alerts

A run whose risk score is **strictly above `CRITICAL_RISK_THRESHOLD`** (default 8, so 9 or 10) emails, immediately when the run completes:

- everyone subscribed to that repo, and
- anyone subscribed globally, which is how `ADMIN_ALERT_EMAIL` is seeded.

There's one global threshold and no per-subscriber override. All mail goes out from the platform's own SMTP account; subscribers only supply a recipient address. Because PR creation now waits for approval, an alert normally has no PR link yet.

---

## Rate limits

The demo runs on free-tier keys, so limits are expected:

- **GitHub:** every request's `X-RateLimit-*` / `Retry-After` headers are recorded.
- **Gemini:** a 429 marks Gemini as limited (with a default 30s window if no `Retry-After` is given). A node hitting a 429 backs off and retries automatically; a *new* pipeline run started while Gemini is known to be limited fails fast instead of spending a call.
- Both are exposed at `GET /api/status/rate-limits` and shown as badges in the dashboard header.

---

## Running tests

```bash
pytest --cov=app
ruff check .
```

The suite needs a Postgres reachable at `DATABASE_URL` (the compose Postgres is fine). Tests that touch the database run inside a transaction that's rolled back afterwards; GitHub and Gemini are mocked throughout. `tests/integration/test_remediation_flow.py` drives the real FastAPI app end to end and includes the automated proof that an inspected repo never reaches the PR-creation code.
