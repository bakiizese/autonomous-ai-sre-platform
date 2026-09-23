# fastapi core server setup
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from app.api import (
    routes_demo,
    routes_issues,
    routes_poll,
    routes_remediation,
    routes_repos,
    routes_status,
    routes_subscribers,
)
from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.agent import PipelineResult, VerificationResult
from app.services.agent_engine import run_sre_pipeline, to_pipeline_result
from app.services.notification_service import seed_admin_subscriber
from app.services.poller_service import poll_loop
from app.services.repo_service import seed_sandbox_repos
from app.services.sandbox_runner import run_preflight_verification

logger = logging.getLogger("sre_pipeline")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        await seed_sandbox_repos(db)
        seed_admin_subscriber(db)

    task = asyncio.create_task(poll_loop())
    logger.info(
        f"🚀 Started background sandbox-repo poller (every {settings.POLL_INTERVAL_SECONDS}s)"
    )
    yield
    task.cancel()
    logger.info("🛑 Stopped background poller")


app = FastAPI(title="Autonomous AI SRE Core Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_repos.router)
app.include_router(routes_issues.router)
app.include_router(routes_remediation.router)
app.include_router(routes_demo.router)
app.include_router(routes_poll.router)
app.include_router(routes_subscribers.router)
app.include_router(routes_status.router)


class TriageRequest(BaseModel):
    error_log: str
    source_code_context: str


class VerificationRequest(BaseModel):
    target_file: str
    remediated_code: str
    test_file_name: str
    generated_test_code: str


@app.get("/")
def read_root():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "online", "service": "Autonomous AI SRE Core Engine", "database": db_status}


@app.post("/api/triage", response_model=PipelineResult)
def triage_issue(request: TriageRequest):
    """Ad hoc scratchpad diagnosis — unpersisted, doesn't touch a repo."""
    try:
        state = run_sre_pipeline(request.error_log, request.source_code_context)
        return to_pipeline_result(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify", response_model=VerificationResult)
def verify_patch(request: VerificationRequest):
    """Ad hoc sandbox check of pasted code — unpersisted."""
    try:
        return run_preflight_verification(
            target_file_rel_path=request.target_file,
            remediated_code=request.remediated_code,
            test_file_name=request.test_file_name,
            generated_test_code=request.generated_test_code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhook/github")
async def github_webhook(request: Request):
    """Placeholder: real detection is poller-driven (settings.POLL_INTERVAL_SECONDS),
    not webhook-driven yet — signature-verified webhook ingestion is a V2 item."""
    payload = await request.json()
    action = payload.get("action")

    if action == "opened" and "issue" in payload:
        issue = payload["issue"]
        logger.info(f"Webhook: issue #{issue['number']} opened (not yet auto-triaged from webhooks)")
        return {"status": "event_received", "issue_number": issue["number"]}

    return {"status": "event_ignored"}
