"""End-to-end tests through the real FastAPI app + routers, with GitHub and
Gemini mocked but the database, service layer, and route wiring all real.

TestClient is used WITHOUT `with` deliberately — entering the context manager
would run main.py's lifespan (seed_sandbox_repos against real GitHub,
poll_loop as a real background task), which we don't want interfering with
an isolated per-test transaction. Skipping `with` means routes still work,
lifespan just never runs.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from app.db.models import Issue, IssueOrigin, RemediationRun, Repo, RepoType, RunStatus
from app.db.session import get_db
from app.schemas.agent import DiagnosisOutput, RemediationOutput, TestGenerationOutput, VerificationResult
from app.services import remediation_service, repo_service

DIAGNOSIS = DiagnosisOutput(summary="s", root_cause_analysis="r", affected_files=["a.py"], risk_score=9)
REMEDIATION = RemediationOutput(patch_explanation="p", target_file="a.py", code_fix="fix", git_diff_patch="diff")
TEST_GEN = TestGenerationOutput(test_file_name="test_a.py", test_code="code", test_description="d")
PASSED_VERIFICATION = VerificationResult(passed=True, target_test_passed=True, stdout="ok", stderr="")


@pytest.fixture(autouse=True)
def no_real_source_lookup():
    """start_remediation_run resolves source context from GitHub; keep tests offline."""
    with patch.object(
        remediation_service,
        "resolve_source_context",
        AsyncMock(return_value={"source_code": "", "resolved_path": None, "method": "not_found"}),
    ):
        yield


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_sandbox_repo_full_loop_reaches_pr_opened(client, db_session):
    """connect (well, seed) -> baseline -> manual triage -> awaiting_approval -> approve -> pr_opened."""
    repo = Repo(owner="o", name="sandbox", full_name="o/sandbox", repo_type=RepoType.sandbox)
    db_session.add(repo)
    db_session.flush()
    issue = Issue(repo_id=repo.id, issue_number=1, title="Bug", body="stack trace", origin=IssueOrigin.baseline)
    db_session.add(issue)
    db_session.commit()

    pipeline_state = {
        "diagnosis": DIAGNOSIS,
        "remediation": REMEDIATION,
        "test_generation": TEST_GEN,
        "verification": PASSED_VERIFICATION,
        "fix_attempt": 1,
        "node_trace": [{"node": "diagnose"}],
    }

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=pipeline_state)), \
         patch.object(remediation_service, "notify_subscribers"):
        resp = client.post(f"/api/repos/{repo.id}/issues/{issue.issue_number}/triage")

    assert resp.status_code == 200, resp.text
    run_data = resp.json()
    assert run_data["status"] == "awaiting_approval"
    assert run_data["pr_url"] is None
    run_id = run_data["id"]

    with patch.object(remediation_service.github_client, "get_default_branch_sha", AsyncMock(return_value="sha1")), \
         patch.object(remediation_service.github_client, "create_branch", AsyncMock(return_value=True)) as mock_branch, \
         patch.object(remediation_service.github_client, "create_or_update_file", AsyncMock()), \
         patch.object(remediation_service.github_client, "create_pull_request", AsyncMock(return_value={"html_url": "http://pr/1", "number": 1})) as mock_pr, \
         patch.object(remediation_service.github_client, "close_issue", AsyncMock()):
        approve_resp = client.post(f"/api/remediation-runs/{run_id}/approve")

    assert approve_resp.status_code == 200, approve_resp.text
    approved = approve_resp.json()
    assert approved["status"] == "pr_opened"
    assert approved["pr_url"] == "http://pr/1"
    mock_branch.assert_called_once()
    mock_pr.assert_called_once()

    persisted = db_session.get(RemediationRun, run_id)
    assert persisted.status == RunStatus.pr_opened


def test_inspected_repo_stops_at_diagnosed_and_never_opens_pr(client, db_session):
    """A read-only inspected repo's run must stop at 'diagnosed' — this is
    the concrete, automated proof of the read-only guarantee: the pipeline
    itself never even generates a fix, and the PR route is never called."""
    with patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(
        repo_service.github_client, "list_open_issues",
        AsyncMock(return_value=[{"number": 3, "title": "Some bug", "body": "trace", "html_url": "u", "created_at": None}]),
    ):
        connect_resp = client.post("/api/repos/connect", json={"full_name": "octocat/read-only-test"})

    assert connect_resp.status_code == 200, connect_resp.text
    repo_id = connect_resp.json()["id"]
    assert connect_resp.json()["repo_type"] == "inspected"

    pipeline_state = {"diagnosis": DIAGNOSIS, "fix_attempt": 0, "node_trace": []}

    with patch.object(remediation_service, "run_sre_pipeline", MagicMock(return_value=pipeline_state)) as mock_pipeline, \
         patch.object(remediation_service, "notify_subscribers"), \
         patch.object(remediation_service.github_client, "create_pull_request", AsyncMock()) as mock_create_pr, \
         patch.object(remediation_service.github_client, "create_branch", AsyncMock()) as mock_create_branch:
        triage_resp = client.post(f"/api/repos/{repo_id}/issues/3/triage")

    assert triage_resp.status_code == 200, triage_resp.text
    run_data = triage_resp.json()
    assert run_data["status"] == "diagnosed"
    assert run_data["target_file"] is None
    assert run_data["pr_url"] is None

    # stop_after_diagnosis=True was passed for this non-sandbox repo
    assert mock_pipeline.call_args.args[2] is True

    mock_create_pr.assert_not_called()
    mock_create_branch.assert_not_called()

    # and there's no awaiting_approval run to even approve
    run_id = run_data["id"]
    approve_resp = client.post(f"/api/remediation-runs/{run_id}/approve")
    assert approve_resp.status_code == 409


def test_baseline_ingestion_does_not_trigger_remediation(client, db_session):
    """Connecting a repo with existing open issues imports them as baseline
    records but must NOT kick off any remediation runs on its own."""
    with patch.object(
        repo_service.github_client, "get_repo", AsyncMock(return_value={"private": False, "default_branch": "main"})
    ), patch.object(
        repo_service.github_client, "list_open_issues",
        AsyncMock(return_value=[
            {"number": 1, "title": "Old bug 1", "body": "", "html_url": "u1", "created_at": None},
            {"number": 2, "title": "Old bug 2", "body": "", "html_url": "u2", "created_at": None},
        ]),
    ), patch.object(remediation_service, "run_sre_pipeline") as mock_pipeline:
        resp = client.post("/api/repos/connect", json={"full_name": "octocat/baseline-test"})

    assert resp.status_code == 200
    repo_id = resp.json()["id"]

    issues_resp = client.get(f"/api/repos/{repo_id}/issues?scope=baseline")
    assert issues_resp.status_code == 200
    assert len(issues_resp.json()) == 2
    assert all(i["latest_remediation_run_id"] is None for i in issues_resp.json())
    mock_pipeline.assert_not_called()
