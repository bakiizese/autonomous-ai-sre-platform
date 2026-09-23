import logging
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.models import Issue, RemediationRun, Repo, RepoType, RunStatus, RunTriggerSource
from app.services.agent_engine import run_sre_pipeline
from app.services.github_client import github_client
from app.services.notification_service import notify_subscribers
from app.services.source_context_service import resolve_source_context

logger = logging.getLogger("sre_pipeline")


class ApprovalError(Exception):
    """Raised when approve/reject is called on a run that isn't awaiting approval."""


async def start_remediation_run(
    db: Session, issue: Issue, repo: Repo, trigger_source: RunTriggerSource
) -> RemediationRun:
    """Runs the full LangGraph pipeline for one issue and persists the
    outcome. For a sandbox repo this diagnoses, fixes, generates a test, and
    sandbox-verifies fully automatically — but it ALWAYS stops at
    'awaiting_approval' rather than opening a PR; approve_remediation_run()
    is the separate, human-confirmed action that actually writes to GitHub.
    For an inspected (read-only) repo, stop_after_diagnosis structurally
    prevents the pipeline from ever generating a fix at all."""
    run = RemediationRun(
        issue_id=issue.id,
        repo_id=repo.id,
        trigger_source=trigger_source,
        status=RunStatus.running,
    )
    db.add(run)
    db.flush()

    error_log = issue.body or issue.title
    stop_after_diagnosis = repo.repo_type != RepoType.sandbox

    # Without the actual source, the model would be rewriting the target file
    # blind from the issue text. Failing to find it isn't fatal, just worse.
    source_context = ""
    try:
        resolved = await resolve_source_context(repo.full_name, issue.body or "")
        if resolved["source_code"]:
            source_context = f"FILE PATH: {resolved['resolved_path']}\n\n{resolved['source_code']}"
    except Exception as e:
        logger.warning(f"[REMEDIATION] Could not resolve source context for issue #{issue.issue_number}: {e}")

    try:
        state = await run_in_threadpool(
            run_sre_pipeline, error_log, source_context, stop_after_diagnosis
        )
    except Exception as e:
        logger.error(f"[REMEDIATION] Run {run.id} for issue #{issue.issue_number} failed: {e}")
        run.status = RunStatus.failed
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        issue.latest_remediation_run_id = run.id
        db.commit()
        return run

    diagnosis = state.get("diagnosis")
    if diagnosis is not None:
        run.risk_score = diagnosis.risk_score
        run.diagnosis_summary = diagnosis.summary
        run.root_cause_analysis = diagnosis.root_cause_analysis
        run.affected_files = diagnosis.affected_files

    remediation = state.get("remediation")
    if remediation is not None:
        run.target_file = remediation.target_file
        run.code_fix = remediation.code_fix
        run.git_diff_patch = remediation.git_diff_patch

    test_generation = state.get("test_generation")
    if test_generation is not None:
        run.test_file_name = test_generation.test_file_name
        run.test_code = test_generation.test_code

    verification = state.get("verification")
    if verification is not None:
        run.verification_passed = verification.passed
        run.verification_stdout = verification.stdout
        run.verification_stderr = verification.stderr

    run.fix_attempts = state.get("fix_attempt", 0)
    run.node_trace = state.get("node_trace", [])
    run.completed_at = datetime.now(timezone.utc)

    if stop_after_diagnosis:
        run.status = RunStatus.diagnosed
    elif verification is not None and verification.passed:
        run.status = RunStatus.awaiting_approval
    elif verification is not None:
        run.status = RunStatus.verify_failed
    else:
        run.status = RunStatus.failed
        run.error_message = "Pipeline ended without a verification result."

    issue.latest_remediation_run_id = run.id
    db.commit()

    if run.risk_score is not None:
        notify_subscribers(db, run)

    return run


async def approve_remediation_run(db: Session, run: RemediationRun) -> RemediationRun:
    """The human-in-the-loop gate: only a run sitting at 'awaiting_approval'
    can be approved, and this is the only code path in the whole system that
    actually opens a branch/commit/PR on GitHub."""
    if run.status != RunStatus.awaiting_approval:
        raise ApprovalError(f"Run {run.id} is '{run.status.value}', not awaiting approval.")

    repo = run.repo
    issue = run.issue

    branch_name = f"fix/issue-{issue.issue_number}-run-{run.id}"
    base_sha = await github_client.get_default_branch_sha(repo.full_name)
    await github_client.create_branch(repo.full_name, branch_name, base_sha)

    await github_client.create_or_update_file(
        repo_full_name=repo.full_name,
        file_path=run.target_file,
        content=run.code_fix,
        commit_message=f"fix: automated patch for issue #{issue.issue_number}",
        branch_name=branch_name,
    )
    await github_client.create_or_update_file(
        repo_full_name=repo.full_name,
        file_path=f"tests/{run.test_file_name}",
        content=run.test_code,
        commit_message=f"test: add automated unit test for issue #{issue.issue_number}",
        branch_name=branch_name,
    )

    pr_result = await github_client.create_pull_request(
        repo_full_name=repo.full_name,
        title=f"fix(sre): automated patch for issue #{issue.issue_number}",
        body=(
            f"Risk score: {run.risk_score}/10\n\n{run.root_cause_analysis}\n\n"
            f"Approved via the Sentinel SRE dashboard (run #{run.id})."
        ),
        head_branch=branch_name,
    )

    await github_client.close_issue(
        repo.full_name,
        issue.issue_number,
        comment=f"🤖 Automatically fixed. See {pr_result.get('html_url')} for the patch and sandbox verification proof.",
    )

    run.status = RunStatus.pr_opened
    run.pr_url = pr_result.get("html_url")
    run.pr_number = pr_result.get("number")
    run.branch_name = branch_name
    run.approved_at = datetime.now(timezone.utc)
    db.commit()
    return run


def reject_remediation_run(db: Session, run: RemediationRun, reason: str | None = None) -> RemediationRun:
    if run.status != RunStatus.awaiting_approval:
        raise ApprovalError(f"Run {run.id} is '{run.status.value}', not awaiting approval.")

    run.status = RunStatus.rejected
    run.error_message = reason
    db.commit()
    return run
