# fastapi core server setup
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.agent_engine import run_sre_pipeline
from app.services.sandbox_runner import run_preflight_verification
from app.schemas.agent import PipelineResult, VerificationResult
from app.services.github_client import github_client
from app.services.email_service import send_critical_alert
from app.services.context_resolver import (
    extract_candidate_file_paths,
    extract_candidate_function_names,
)

logger = logging.getLogger("sre_pipeline")
logging.basicConfig(level=logging.INFO)

# --- Background polling worker ---
seen_issue_numbers: set[int] = set()
POLL_INTERVAL_SECONDS = 60
CRITICAL_RISK_THRESHOLD = 7


async def poll_github_issues():
    """Background loop: checks for new open GitHub issues every 60s."""
    global seen_issue_numbers
    is_first_run = True

    while True:
        try:
            issues = await github_client.list_open_issues()
            current_numbers = {issue["number"] for issue in issues}

            if not is_first_run:
                new_numbers = current_numbers - seen_issue_numbers
                for issue in issues:
                    if issue["number"] in new_numbers:
                        logger.info(
                            f"[POLLER] 🆕 New issue detected: #{issue['number']} - {issue['title']}"
                        )
                        asyncio.create_task(auto_remediate_issue(issue))
            else:
                logger.info(
                    f"[POLLER] 🔍 Initial poll baseline: {len(current_numbers)} open issue(s) recorded."
                )
                is_first_run = False

            seen_issue_numbers = current_numbers

        except Exception as e:
            logger.error(f"[POLLER] ⚠️ Polling error: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def auto_remediate_issue(issue: dict):
    """Triggered automatically when a new issue is detected. Runs the full loop."""
    try:
        logger.info(f"[POLLER] 🤖 Auto-remediation starting for issue #{issue['number']}")

        error_log = issue.get("body", "") or issue.get("title", "")
        source_code_context = ""  # no source context available from issue text alone

        pipeline_result = await run_in_threadpool(
            run_sre_pipeline, error_log, source_code_context
        )

        is_critical = pipeline_result.diagnosis.risk_score > CRITICAL_RISK_THRESHOLD

        verification = await run_in_threadpool(
            run_preflight_verification,
            target_file_rel_path=pipeline_result.remediation.target_file,
            remediated_code=pipeline_result.remediation.code_fix,
            test_file_name=pipeline_result.test_generation.test_file_name,
            generated_test_code=pipeline_result.test_generation.test_code,
        )

        if not verification.passed:
            logger.warning(
                f"[POLLER] ❌ Auto-remediation for #{issue['number']} failed sandbox verification: {verification.stderr}"
            )
            if is_critical:
                await run_in_threadpool(
                    send_critical_alert,
                    issue["number"],
                    issue["title"],
                    pipeline_result.diagnosis.risk_score,
                    pipeline_result.diagnosis.root_cause_analysis,
                    None,
                )
            return

        branch_name = f"fix/issue-{issue['number']}-auto-remediation"
        base_sha = await github_client.get_default_branch_sha()
        await github_client.create_branch(branch_name, base_sha)

        await github_client.create_or_update_file(
            file_path=pipeline_result.remediation.target_file,
            content=pipeline_result.remediation.code_fix,
            commit_message=f"fix: automated patch for issue #{issue['number']}",
            branch_name=branch_name,
        )

        await github_client.create_or_update_file(
            file_path=f"tests/{pipeline_result.test_generation.test_file_name}",
            content=pipeline_result.test_generation.test_code,
            commit_message=f"test: add automated unit test for issue #{issue['number']}",
            branch_name=branch_name,
        )

        pr_result = await github_client.create_pull_request(
            title=f"fix(sre): automated patch for Issue #{issue['number']}",
            body=f"Auto-generated fix for issue #{issue['number']}.\n\nRisk Score: {pipeline_result.diagnosis.risk_score}/10\n\n{pipeline_result.diagnosis.root_cause_analysis}",
            head_branch=branch_name,
        )

        logger.info(f"[POLLER] ✅ Auto-remediation PR opened: {pr_result.get('html_url')}")

        await github_client.close_issue(
            issue["number"],
            comment=f"🤖 Automatically fixed by Sentinel SRE. See {pr_result.get('html_url')} for the patch and sandbox verification proof.",
        )
        logger.info(f"[POLLER] 🔒 Closed issue #{issue['number']}")

        if is_critical:
            await run_in_threadpool(
                send_critical_alert,
                issue["number"],
                issue["title"],
                pipeline_result.diagnosis.risk_score,
                pipeline_result.diagnosis.root_cause_analysis,
                pr_result.get("html_url"),
            )

    except Exception as e:
        logger.error(f"[POLLER] ⚠️ Auto-remediation failed for issue #{issue['number']}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_github_issues())
    logger.info(
        f"🚀 Started background GitHub issue poller (every {POLL_INTERVAL_SECONDS}s)"
    )
    yield
    task.cancel()
    logger.info("🛑 Stopped background GitHub issue poller")


app = FastAPI(title="Autonomous AI SRE Core Engine", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    error_log: str
    source_code_context: str


class VerificationRequest(BaseModel):
    target_file: str
    remediated_code: str
    test_file_name: str
    generated_test_code: str


class PRAutomationRequest(BaseModel):
    issue_number: int
    error_log: str
    source_code_context: str


@app.get("/")
def read_root():
    return {"status": "online", "service": "Autonomous AI SRE Core Engine"}


@app.post("/api/triage", response_model=PipelineResult)
def triage_issue(request: TriageRequest):
    try:
        return run_sre_pipeline(request.error_log, request.source_code_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/issues")
async def get_issues():
    try:
        issues = await github_client.list_open_issues()
        return {"issues": issues}
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch GitHub issues: {e}"
        )


@app.post("/api/verify", response_model=VerificationResult)
def verify_patch(request: VerificationRequest):
    try:
        return run_preflight_verification(
            target_file_rel_path=request.target_file,
            remediated_code=request.remediated_code,
            test_file_name=request.test_file_name,
            generated_test_code=request.generated_test_code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/remediate-and-pr")
async def remediate_and_open_pr(request: PRAutomationRequest):
    """Full end-to-end automation loop: Triage -> Sandbox Verification -> GitHub PR."""
    try:
        pipeline_result = await run_in_threadpool(
            run_sre_pipeline, request.error_log, request.source_code_context
        )
        verification = await run_in_threadpool(
            run_preflight_verification,
            target_file_rel_path=pipeline_result.remediation.target_file,
            remediated_code=pipeline_result.remediation.code_fix,
            test_file_name=pipeline_result.test_generation.test_file_name,
            generated_test_code=pipeline_result.test_generation.test_code,
        )

        if not verification.passed:
            raise HTTPException(
                status_code=422,
                detail=f"Pre-flight sandbox checks failed: {verification.stderr}",
            )

        branch_name = f"fix/issue-{request.issue_number}-auto-remediation"
        base_sha = await github_client.get_default_branch_sha()

        await github_client.create_branch(branch_name, base_sha)
        await github_client.create_or_update_file(
            file_path=pipeline_result.remediation.target_file,
            content=pipeline_result.remediation.code_fix,
            commit_message=f"fix: automated patch for issue #{request.issue_number}",
            branch_name=branch_name,
        )

        await github_client.create_or_update_file(
            file_path=f"tests/{pipeline_result.test_generation.test_file_name}",
            content=pipeline_result.test_generation.test_code,
            commit_message=f"test: add automated unit test for issue #{request.issue_number}",
            branch_name=branch_name,
        )

        pr_body = f"""## 🤖 Autonomous SRE Remediation Report

                **Issue ID:** #{request.issue_number}
                **Risk Score:** {pipeline_result.diagnosis.risk_score}/10

                #### 📌 Root Cause Analysis
                {pipeline_result.diagnosis.root_cause_analysis}

                #### 🛠️ Fix Description
                {pipeline_result.remediation.patch_explanation}

                #### 🧪 Pre-Flight Execution Log
```text
                {verification.stdout if verification.stdout else 'Pytest passed successfully in sandbox.'}
```
                """
        pr_result = await github_client.create_pull_request(
            title=f"fix(sre): automated patch for Issue #{request.issue_number}",
            body=pr_body,
            head_branch=branch_name,
        )

        await github_client.close_issue(
            request.issue_number,
            comment=f"🤖 Automatically fixed. See {pr_result.get('html_url')} for the patch and sandbox verification proof.",
        )
        logger.info(f"[MANUAL] 🔒 Closed issue #{request.issue_number}")

        if pipeline_result.diagnosis.risk_score > CRITICAL_RISK_THRESHOLD:
            await run_in_threadpool(
                send_critical_alert,
                request.issue_number,
                f"Issue #{request.issue_number}",
                pipeline_result.diagnosis.risk_score,
                pipeline_result.diagnosis.root_cause_analysis,
                pr_result.get("html_url"),
            )

        return {
            "status": "success",
            "pr_url": pr_result.get("html_url"),
            "pr_number": pr_result.get("number"),
            "branch": branch_name,
            "verification": verification,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhook/github")
async def github_webhook(request: Request):
    """Listens for automated event payloads directly from GitHub."""
    payload = await request.json()
    action = payload.get("action")

    if action == "opened" and "issue" in payload:
        issue = payload["issue"]
        print(f"🤖 Automatic SRE Triggered for Issue #{issue['number']}")
        return {"status": "auto_triage_started", "issue_number": issue["number"]}

    return {"status": "event_ignored"}


@app.get("/api/issues/{issue_number}/context")
async def get_issue_context(issue_number: int):
    """Best-effort auto-resolution of the source file relevant to a GitHub issue."""
    issue = await github_client.get_issue(issue_number)
    body = issue.get("body", "") or ""

    # Tier 1: issue body mentions an explicit file path
    for path in extract_candidate_file_paths(body):
        content = await github_client.get_file_content(path)
        if content:
            return {
                "source_code": content,
                "resolved_path": path,
                "method": "direct_path",
            }

    # Tier 2: issue body mentions a function name — search the repo for it
    for func_name in extract_candidate_function_names(body):
        results = await github_client.search_code(func_name)
        if results:
            path = results[0]["path"]
            content = await github_client.get_file_content(path)
            if content:
                return {
                    "source_code": content,
                    "resolved_path": path,
                    "method": "code_search",
                }

    return {"source_code": "", "resolved_path": None, "method": "not_found"}
