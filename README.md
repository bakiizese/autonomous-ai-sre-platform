# 🛡️ Autonomous AI SRE & Code Remediation Platform

A human-governed AI Reliability Engineer built on Gemini, LangGraph, FastAPI, PostgreSQL and React. It picks up GitHub issues, diagnoses them, generates a fix and a test for it, verifies both in an isolated sandbox, and then waits for a person to approve before anything is written to GitHub.

This is a working demo. A production-grade V2 (accounts and GitHub OAuth, multi-tenant isolation, signed webhooks, a real job queue, audit logging) is planned and is what the landing page teases.

---

## 🌟 Overview & System Features

* **🤖 Multi-agent graph:** A LangGraph state graph of diagnose → fix → test-generation → verify nodes. Each node makes one structured Gemini call, retries on rate limits and malformed output, and a failed verification loops back for one self-corrected retry.
* **🧪 Sandboxed verification:** Generated fixes and tests are run with `pytest` in a throwaway temp directory before anyone is asked to look at them.
* **✋ Human-in-the-loop:** Fixes stop at an "awaiting approval" state. The only code path that opens a branch or PR is the explicit approve action.
* **🔒 Read-only inspection:** Visitors can connect any public repo. Those runs stop after diagnosis — the pipeline never even generates a fix, let alone writes to the repo. Only repos listed in `SANDBOX_REPOS` are writable.
* **🐙 GitHub workflow automation:** Branch, commit, and PR creation with the diagnosis and sandbox proof attached; issues are polled every 30s (or on demand) and existing issues are ingested as a baseline instead of being fixed in bulk.
* **📧 Critical-risk alerts:** Anyone can subscribe an email to a repo and gets an alert the moment a diagnosis scores above 8/10. No accounts.
* **📈 Rate-limit awareness:** The demo runs on free-tier keys, so Gemini and GitHub rate limits are tracked and shown in the dashboard header.
* **📊 Dashboard:** React + TypeScript console with a repo selector, issue list, approval queue and review modal, agent-graph trace per run, and a one-click "inject a bug" demo.

Want to see it work? Point `SANDBOX_REPOS` at [`bakiizese/sentinel-sre-playground`](https://github.com/bakiizese/sentinel-sre-playground) — a small repo of intentionally broken modules — and use **Inject a bug** in the dashboard.

---

## 🏗️ System Architecture

```text
┌────────────────┐    HTTP / JSON    ┌──────────────────────────────────┐
│ React Frontend │ ────────────────▶ │       FastAPI Core Engine        │
│ (nginx :5173)  │ ◀──────────────── │            (:8000)               │
└────────────────┘                   └───────┬──────────────────┬───────┘
                                             │                  │
                                             ▼                  ▼
                               ┌───────────────────┐   ┌──────────────────┐
                               │    PostgreSQL     │   │ Background poller│
                               │ repos · issues ·  │◀──│ (sandbox repos,  │
                               │ runs · subscribers│   │  every 30s)      │
                               └───────────────────┘   └────────┬─────────┘
                                                                │
                              LangGraph agent graph  ◀──────────┘
                ┌──────────┐   ┌─────┐   ┌──────────┐   ┌────────┐
                │ diagnose │──▶│ fix │──▶│ test_gen │──▶│ verify │──┐ fail → back to fix (once)
                └──────────┘   └─────┘   └──────────┘   └────────┘  │
                     │ (read-only repos stop here)                  ▼ pass
                     ▼                                     awaiting_approval
                  diagnosed                                         │ human clicks approve
                                                                    ▼
                                                     GitHub: branch → commit → PR
```

---

## 📂 Repository Layout

```text
.
├── backend/              # FastAPI app, LangGraph agent, services, Alembic migrations, tests
├── frontend/             # React 19 + Vite dashboard and landing page
├── docker-compose.yml    # postgres + backend + frontend
└── .github/workflows/    # CI: backend tests/lint, frontend build, docker build
```

---

## 🚀 Quick Start Guide

### Option A — Docker (recommended)

```bash
cp backend/.env.example backend/.env
# edit backend/.env — at minimum set GEMINI_API_KEY, GITHUB_TOKEN and SANDBOX_REPOS

docker compose up --build
```

* Dashboard: `http://localhost:5173`
* API + Swagger UI: `http://localhost:8000/docs`
* Postgres is exposed on host port `5433` (so it doesn't clash with a local Postgres). Migrations are applied automatically when the backend container starts.

`VITE_API_BASE_URL` is baked into the frontend bundle at build time and must be an address the *browser* can reach (default `http://localhost:8000`). Set it in your shell before `docker compose up --build` if you're serving the API from somewhere else.

### Option B — Run the pieces yourself

Prerequisites: Python 3.12, Node.js 20+, Docker (for Postgres), a Google AI Studio API key, and a GitHub PAT that can write to your sandbox repo.

```bash
# Postgres
docker compose up -d postgres

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then fill in your keys
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`.

### Hosting it

See [`DEPLOY.md`](DEPLOY.md) for a free-tier setup on Render + Neon, including what to know before making it public.

### Configuration

The important variables (full list and notes in [`backend/README.md`](backend/README.md)):

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key (required) |
| `GEMINI_MODEL_ID` | Model to use (default `gemini-2.5-flash`) |
| `GITHUB_TOKEN` | PAT used for every GitHub call — read-only inspection and sandbox writes alike |
| `SANDBOX_REPOS` | Comma-separated `owner/repo` list the platform may write to |
| `DATABASE_URL` | Postgres connection string |
| `POLL_INTERVAL_SECONDS` | Sandbox-repo poll interval (default 30) |
| `CRITICAL_RISK_THRESHOLD` | Alert when risk score is strictly above this (default 8) |
| `SMTP_*`, `ADMIN_ALERT_EMAIL` | Outgoing mail, and the owner address that's always alerted |

---

## ✅ Development

```bash
cd backend && pytest --cov=app        # needs Postgres on DATABASE_URL
cd backend && ruff check .
cd frontend && npm run lint && npm run typecheck && npm run build
```

CI runs all of this on every pull request.

---

## 📄 License & Attribution

Distributed under the MIT License. Built for autonomous systems engineering, reliability testing, and developer productivity workflows.
