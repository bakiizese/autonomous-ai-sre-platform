# ⚙️ Autonomous AI SRE — Backend Service

The backend engine for the Autonomous AI SRE Platform. It watches a GitHub
repository for new issues, diagnoses them with Gemini, verifies a generated
fix in an isolated sandbox, and — if the fix passes — opens a pull request
automatically. Critical-risk issues also trigger an email alert.

Nothing merges without a human: the pipeline stops at "PR opened," it never
approves or merges its own work.

---

## How it actually works

```text
GitHub issue created
        │
        ▼
Background poller (every 60s) detects it
        │
        ▼
Gemini triage — single structured call returns:
  • diagnosis (root cause + risk score 1–10)
  • a code fix + git diff
  • a generated pytest file
        │
        ▼
Sandbox runner executes the generated test
against the generated fix, in a throwaway
temp directory
        │
   ┌────┴────┐
   ▼         ▼
 PASS       FAIL
   │         │
   │         └─► logged as failed, no PR opened
   │             (if risk > 7, alert email sent anyway)
   ▼
GitHub client:
  • creates a branch
  • commits the fix + the test file
  • opens a pull request
  • comments on and closes the original issue
        │
        ▼
If risk score > 7 → critical alert email sent
```

You can also trigger this manually from the dashboard (`/api/remediate-and-pr`)
for a specific issue instead of waiting on the poller, and you can run just the
diagnosis step (`/api/triage`) without touching GitHub at all.

---

## Tech stack

| Layer | What it uses |
|---|---|
| API framework | FastAPI on Python 3.12, served by Uvicorn |
| AI engine | `google-genai` SDK — model ID is set directly in `agent_engine.py` (`MODEL_ID`), not via env var |
| Structured output | Pydantic v2 schemas (`app/schemas/agent.py`) |
| Sandbox | `tempfile.TemporaryDirectory` + `subprocess` running `pytest`, with a timeout |
| GitHub integration | `httpx` against the GitHub REST API — branches, commits, PRs, issue comments/closing |
| Email alerts | `smtplib` over SMTP (Gmail requires an **App Password**, not your account password — see below) |
| Background jobs | An `asyncio` task started in the FastAPI `lifespan`, polling every 60s |

---

## Directory structure

```text
backend/
├── app/
│   ├── core/
│   │   └── config.py         # pydantic-settings — all env vars load here
│   ├── schemas/
│   │   └── agent.py          # DiagnosisOutput, RemediationOutput, TestGenerationOutput,
│   │                          # PipelineResult, VerificationResult
│   └── services/
│       ├── agent_engine.py       # Gemini call + structured triage
│       ├── context_resolver.py   # best-effort file/function extraction from issue text
│       ├── email_service.py      # critical alert emails
│       ├── github_client.py      # all GitHub REST calls
│       └── sandbox_runner.py     # isolated pytest execution
├── main.py                   # FastAPI app, routes, and the background poller
├── requirements.txt
└── tests/
```

All API routes currently live directly in `main.py` — there is no separate
`app/api/` router module yet.

---

## Getting started

### 1. Prerequisites

- Python 3.12
- A GitHub Personal Access Token with `repo` scope
- A Google AI Studio API key
- (Optional, for critical alerts) an SMTP account — see the Gmail note below

### 2. Install

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure `.env`

**Create this file inside `backend/`, not the repo root** — `pydantic-settings`
resolves `.env` relative to your current working directory when you launch
the server, so if you `uvicorn` from the wrong folder these values silently
fail to load.

These names match `config.py` exactly — using different names (e.g.
`GITHUB_REPO_OWNER`/`GITHUB_REPO_NAME` instead of a single `GITHUB_REPO`)
will not work:

```env
# Required
GEMINI_API_KEY=your_google_ai_studio_api_key
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_REPO=your-username/your-repo        # single "owner/repo" string

# Optional
PORT=8000

# Critical-alert email (skipped silently if SMTP_HOST or ALERT_EMAIL_TO is unset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password    # no spaces — see note below
ALERT_EMAIL_TO=lead_engineer@example.com
ALERT_EMAIL_FROM=your_email@gmail.com      # defaults to SMTP_USER if omitted
```

> **Gmail specifically:** you cannot use your normal account password here —
> Gmail rejects it with a `535 Username and Password not accepted` error.
> Enable 2-Step Verification, then generate an
> [App Password](https://myaccount.google.com/apppasswords) and paste that
> in instead, with the spaces removed.

### 4. Run

```bash
uvicorn main:app --reload --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- The background poller starts automatically and logs a startup line —
  watch for `🚀 Started background GitHub issue poller` to confirm it's alive.

---

## API routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| GET | `/api/issues` | List open GitHub issues (PRs filtered out) |
| GET | `/api/issues/{issue_number}/context` | Best-effort auto-resolve source code relevant to an issue |
| POST | `/api/triage` | Run diagnosis + fix + test generation only, no GitHub writes |
| POST | `/api/verify` | Run sandbox pytest verification on arbitrary code/test input |
| POST | `/api/remediate-and-pr` | Full loop for a specific issue: triage → sandbox → branch → commit → PR → close issue |
| POST | `/api/webhook/github` | Placeholder GitHub webhook receiver |

---

## The background poller

Runs on a fixed 60-second interval, comparing the current list of open
issues against what it saw last cycle. Any issue number that's new since
the last poll triggers the full remediation loop automatically, the same
as clicking "Full Loop & Open PR" in the dashboard.

**Risk-based alerting:** a diagnosis risk score above 7 (i.e. 8, 9, or 10)
triggers a critical email alert — on a sandbox verification failure *and*
on a successful PR. Anything 7 or below never sends an email; that's
expected, not a bug.

---

## Running tests

```bash
pytest
```