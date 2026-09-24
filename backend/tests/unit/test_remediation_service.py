from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import Issue, IssueOrigin, RemediationRun, Repo, RepoType, RunStatus, RunTriggerSource
from app.schemas.agent import DiagnosisOutput, RemediationOutput, TestGenerationOutput, VerificationResult
from app.services import remediation_service


def _make_issue(db_session, repo_type):
    repo = Repo(owner="o", name="r", full_name="o/r", repo_type=repo_type)
    db_session.add(repo)
    db_session.flush()
    issue = Issue(repo_id=repo.id, issue_number=5, title="boom", body="stack trace", origin=IssueOrigin.baseline)
    db_session.add(issue)
    db_session.commit()
    return repo, issue


@pytest.fixture(autouse=True)
def no_real_source_lookup():
    """start_remediation_run resolves source context from GitHub; keep tests offline."""
    with patch.object(
        remediation_service,
        "resolve_source_context",
        AsyncMock(return_value={"source_code": "", "resolved_path": None, "method": "not_found"}),
    ):
        yield


DIAGNOSIS = DiagnosisOutput(summary="s", root_cause_analysis="r", affected_files=["a.py"], risk_score=9)
REMEDIATION = RemediationOutput(patch_explanation="p", target_file="a.py", code_fix="fix", git_diff_patch="diff")
TEST_GEN = TestGenerationOutput(test_file_name="test_a.py", test_code="code", test_description="d")


@pytest.mark.asyncio
async def test_start_remediation_run_inspected_repo_stops_at_diagnosed(db_session):
    repo, issue = _make_issue(db_session, RepoType.inspected)
    state = {"diagnosis": DIAGNOSIS, "fix_attempt": 0, "node_trace": []}

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=state)) as mock_pipeline, \
         patch.object(remediation_service, "notify_subscribers") as mock_notify:
        run = await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.manual_dashboard)

        assert run.status == RunStatus.diagnosed
        assert run.risk_score == 9
        assert run.target_file is None  # no fix was ever generated
        # stop_after_diagnosis=True is passed for a non-sandbox repo
        assert mock_pipeline.call_args.args[2] is True
        mock_notify.assert_called_once()
        assert issue.latest_remediation_run_id == run.id


@pytest.mark.asyncio
async def test_start_remediation_run_sandbox_verify_passed_awaits_approval(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    state = {
        "diagnosis": DIAGNOSIS,
        "remediation": REMEDIATION,
        "test_generation": TEST_GEN,
        "verification": VerificationResult(passed=True, target_test_passed=True, stdout="ok", stderr=""),
        "fix_attempt": 1,
        "node_trace": [{"node": "diagnose"}],
    }

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=state)), \
         patch.object(remediation_service, "notify_subscribers"):
        run = await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.poller)

        assert run.status == RunStatus.awaiting_approval
        assert run.target_file == "a.py"
        assert run.pr_url is None


@pytest.mark.asyncio
async def test_start_remediation_run_sandbox_verify_failed(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    state = {
        "diagnosis": DIAGNOSIS,
        "remediation": REMEDIATION,
        "test_generation": TEST_GEN,
        "verification": VerificationResult(passed=False, target_test_passed=False, stdout="", stderr="still broken"),
        "fix_attempt": 2,
        "node_trace": [],
    }

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=state)), \
         patch.object(remediation_service, "notify_subscribers"):
        run = await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.poller)

        assert run.status == RunStatus.verify_failed


@pytest.mark.asyncio
async def test_start_remediation_run_pipeline_exception_marks_failed(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(side_effect=RuntimeError("gemini exploded"))):
        run = await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.manual_dashboard)

        assert run.status == RunStatus.failed
        assert "gemini exploded" in run.error_message
        assert issue.latest_remediation_run_id == run.id


@pytest.mark.asyncio
async def test_approve_remediation_run_opens_pr(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    run = RemediationRun(
        issue_id=issue.id, repo_id=repo.id, trigger_source=RunTriggerSource.poller,
        status=RunStatus.awaiting_approval, risk_score=9,
        target_file="a.py", code_fix="fix", test_file_name="test_a.py", test_code="code",
        root_cause_analysis="r",
    )
    db_session.add(run)
    db_session.commit()

    with patch.object(remediation_service.github_client, "get_default_branch_sha", AsyncMock(return_value="sha1")), \
         patch.object(remediation_service.github_client, "create_branch", AsyncMock(return_value=True)) as mock_branch, \
         patch.object(remediation_service.github_client, "create_or_update_file", AsyncMock()) as mock_file, \
         patch.object(remediation_service.github_client, "create_pull_request", AsyncMock(return_value={"html_url": "http://pr/1", "number": 1})), \
         patch.object(remediation_service.github_client, "close_issue", AsyncMock()) as mock_close:
        result = await remediation_service.approve_remediation_run(db_session, run)

        assert result.status == RunStatus.pr_opened
        assert result.pr_url == "http://pr/1"
        assert result.pr_number == 1
        assert result.approved_at is not None
        mock_branch.assert_called_once_with(repo.full_name, result.branch_name, "sha1")
        assert mock_file.call_count == 2
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_approve_remediation_run_rejects_wrong_status(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    run = RemediationRun(issue_id=issue.id, repo_id=repo.id, trigger_source=RunTriggerSource.poller, status=RunStatus.diagnosed)
    db_session.add(run)
    db_session.commit()

    with pytest.raises(remediation_service.ApprovalError):
        await remediation_service.approve_remediation_run(db_session, run)


def test_reject_remediation_run_happy_path(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    run = RemediationRun(issue_id=issue.id, repo_id=repo.id, trigger_source=RunTriggerSource.poller, status=RunStatus.awaiting_approval)
    db_session.add(run)
    db_session.commit()

    result = remediation_service.reject_remediation_run(db_session, run, reason="not worth it")

    assert result.status == RunStatus.rejected
    assert result.error_message == "not worth it"


def test_reject_remediation_run_rejects_wrong_status(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    run = RemediationRun(issue_id=issue.id, repo_id=repo.id, trigger_source=RunTriggerSource.poller, status=RunStatus.pr_opened)
    db_session.add(run)
    db_session.commit()

    with pytest.raises(remediation_service.ApprovalError):
        remediation_service.reject_remediation_run(db_session, run)


@pytest.mark.asyncio
async def test_start_remediation_run_passes_resolved_source_to_pipeline(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    state = {"diagnosis": DIAGNOSIS, "fix_attempt": 0, "node_trace": []}
    found = {"source_code": "def buggy(): pass", "resolved_path": "demo/x.py", "method": "direct_path"}

    with patch.object(remediation_service, "resolve_source_context", AsyncMock(return_value=found)), \
         patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=state)) as mock_pipeline, \
         patch.object(remediation_service, "notify_subscribers"):
        await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.poller)

        passed_context = mock_pipeline.call_args.args[1]
        assert "FILE PATH: demo/x.py" in passed_context
        assert "def buggy(): pass" in passed_context


@pytest.mark.asyncio
async def test_start_remediation_run_survives_source_lookup_failure(db_session):
    repo, issue = _make_issue(db_session, RepoType.sandbox)
    state = {
        "diagnosis": DIAGNOSIS,
        "remediation": REMEDIATION,
        "test_generation": TEST_GEN,
        "verification": VerificationResult(passed=True, target_test_passed=True, stdout="ok", stderr=""),
        "fix_attempt": 1,
        "node_trace": [],
    }

    with patch.object(remediation_service, "resolve_source_context", AsyncMock(side_effect=RuntimeError("github down"))), \
         patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=state)) as mock_pipeline, \
         patch.object(remediation_service, "notify_subscribers"):
        run = await remediation_service.start_remediation_run(db_session, issue, repo, RunTriggerSource.poller)

        assert mock_pipeline.call_args.args[1] == ""
        assert run.status == RunStatus.awaiting_approval
