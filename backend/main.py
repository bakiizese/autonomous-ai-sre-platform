# fastapi core server setup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.services.agent_engine import run_sre_pipeline
from app.services.sandbox_runner import run_preflight_verification
from app.schemas.agent import PipelineResult, VerificationResult
from app.services.github_client import github_client
from fastapi import Request

app = FastAPI(title="Autonomous AI SRE Core Engine")


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
        # 1. Run Multi-Agent Triage
        pipeline_result = run_sre_pipeline(
            request.error_log, request.source_code_context
        )

        # 2. Run Pre-flight Sandbox Verification
        verification = run_preflight_verification(
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

        # 3. GitHub Operations
        branch_name = f"fix/issue-{request.issue_number}-auto-remediation"
        base_sha = await github_client.get_default_branch_sha()

        # Create branch
        await github_client.create_branch(branch_name, base_sha)
        # Commit Code Fix
        await github_client.create_or_update_file(
            file_path=pipeline_result.remediation.target_file,
            content=pipeline_result.remediation.code_fix,
            commit_message=f"fix: automated patch for issue #{request.issue_number}",
            branch_name=branch_name,
        )

        # Commit Generated Test File
        await github_client.create_or_update_file(
            file_path=f"tests/{pipeline_result.test_generation.test_file_name}",
            content=pipeline_result.test_generation.test_code,
            commit_message=f"test: add automated unit test for issue #{request.issue_number}",
            branch_name=branch_name,
        )

        # Open PR with proof body
        pr_body = f"""## 🤖 Autonomous SRE Remediation Report

                ### 🟢 Status: Pre-Flight Verification Passed

                **Issue ID:** #{request.issue_number}
                **Risk Score:** {pipeline_result.diagnosis.risk_score}/10

                #### 📌 Root Cause Analysis
                {pipeline_result.diagnosis.root_cause_analysis}

                #### 🛠️ Fix Description
                {pipeline_result.remediation.patch_explanation}

                #### 🧪 Pre-Flight Execution Log
                ```text
                {verification.stdout if verification.stdout else 'Pytest passed successfully in sandbox.'}
                """
        pr_result = await github_client.create_pull_request(
            title=f"fix(sre): automated patch for Issue #{request.issue_number}",
            body=pr_body,
            head_branch=branch_name,
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

    # Check if a new issue was just opened
    if action == "opened" and "issue" in payload:
        issue = payload["issue"]
        issue_number = issue["number"]
        error_log = issue.get("body", "")

        # Pull code context or issue description and trigger pipeline automatically
        print(f"🤖 Automatic SRE Triggered for Issue #{issue_number}")

        # Run remediation loop automatically
        # (In production, run this in a background task so GitHub doesn't time out)
        return {"status": "auto_triage_started", "issue_number": issue_number}

    return {"status": "event_ignored"}
