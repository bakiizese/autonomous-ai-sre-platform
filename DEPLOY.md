# Deploying the demo

The cheapest always-available setup, at $0/month:

| Piece | Where | Why |
|---|---|---|
| Frontend | Render **static site** | Free, never sleeps, serves the SPA |
| Backend | Render **web service** (Docker) | Runs the FastAPI app, agent graph and sandbox |
| Database | **Neon** free Postgres | Doesn't expire — Render's free Postgres is deleted after ~30 days |

`render.yaml` in the repo describes both Render services, so setup is mostly filling in secrets.

## 1. Before you start

- A GitHub token limited to `sentinel-sre-playground` with **Issues**, **Contents** and **Pull requests** read/write (ideally a separate token from the one in your local `.env`, so you can revoke the public one on its own).
- A Google AI Studio key. Consider a dedicated key for the public demo so a leak or a burst of traffic can't affect anything else.
- Accounts on [Neon](https://neon.tech) and [Render](https://render.com).

## 2. Database (Neon)

1. Create a project, then copy the **connection string** (it starts `postgresql://…` and includes `sslmode=require`).
2. Keep it handy — you'll paste it into Render as `DATABASE_URL`. The app rewrites `postgres://`/`postgresql://` to the `psycopg` driver itself, and applies migrations on every start.

## 3. Render

1. **New → Blueprint**, select this repository. Render reads `render.yaml` and proposes two services.
2. Fill the prompted secrets on **sentinel-sre-api**: `GEMINI_API_KEY`, `GITHUB_TOKEN`, `DATABASE_URL`. SMTP / `ADMIN_ALERT_EMAIL` are optional (only needed for alert emails).
3. Apply. Note the two URLs Render assigns (defaults: `https://sentinel-sre-api.onrender.com` and `https://sentinel-sre-web.onrender.com` — yours may differ if a name was taken).
4. Wire them together — this is a second pass because each side needs the other's URL:
   - On **sentinel-sre-web**: set `VITE_API_BASE_URL` to the **api** URL. It's baked into the bundle at build time, so **redeploy** the web service after setting it.
   - On **sentinel-sre-api**: set `ALLOWED_ORIGINS` to the **web** URL (no trailing slash). The service restarts on save.

## 4. Check it

```bash
curl https://<your-api>.onrender.com/            # → "database": "connected"
```

Then open the web URL, choose the playground repo, and click **Inject a bug**. The first request after idle is slow (see below).

## Things to know

- **Free web services sleep after ~15 minutes idle.** The first visitor waits up to a minute for a cold start, and the background poller doesn't run while asleep. Button-driven actions (inject, triage) still work because they run inside the request. To keep it awake, either upgrade the api service to the $7 Starter plan or point a free uptime monitor (e.g. UptimeRobot) at `https://<your-api>.onrender.com/` every 5 minutes.
- **Free-tier API quota is the real limit.** Gemini's free tier has small per-minute and per-day caps; the header badges show when it's exhausted. The app also caps itself (`DAILY_RUN_CAP`, per-visitor rate limits) so one visitor can't burn the day's quota.
- **Rate-limit counters live in memory**, so they reset on every restart/sleep and only work with a single instance. Fine for a demo; V2 would move them to Redis.
- **Sandbox isolation is process-level, not a container.** Generated code runs with a scrubbed environment, resource limits and as an unprivileged user, but can still make outbound network calls. See `backend/README.md` → "Running this in public".
- **Rotate keys** if you ever suspect a leak: revoke the GitHub token and Gemini key, create new ones, update them in Render.
- **The playground repo is public**, so anyone can open issues on it and the poller will pick them up. The daily run cap bounds the cost, and nothing is written to GitHub without your approval in the dashboard. Watch the repo's issue list occasionally and delete spam.

## Updating

Pushes to `main` redeploy both services automatically. Migrations run on each API start.

## If the blueprint doesn't apply cleanly

`render.yaml` couldn't be validated against Render from here, so if a field is rejected, create the two services by hand with the same settings: a Docker web service (root `backend`, health check path `/`) and a static site (root `frontend`, build `npm ci && npm run build`, publish `dist`, plus a rewrite rule `/*` → `/index.html`), with the environment variables listed in `render.yaml`.
