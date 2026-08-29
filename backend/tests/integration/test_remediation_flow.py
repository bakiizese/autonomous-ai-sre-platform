"""
Integration tests for the Autonomous AI SRE Platform backend.

Run from the `backend/` directory:
    pytest tests/ -v

Design notes
------------
- These go through `TestClient`, so routing, request validation, response
  schemas, and status codes are all genuinely exercised end-to-end — not
  just the underlying functions in isolation.
- Gemini (`run_sre_pipeline`) and the GitHub REST client are mocked at the
  boundary. Hitting them for real in a test suite is slow, flaky, costs
  API quota, and — for the "remediate and PR" tests — would actually open
  branches/PRs against a live repo every test run.
- The sandbox (`run_preflight_verification`) is intentionally NOT mocked.
  It's a local, fast, fully isolated subprocess call — mocking it would
  mean the tests no longer prove the pipeline's actual safety gate works,
  which is the single most important guarantee this system makes.
- `client` does NOT use `TestClient(app)` as a context manager, so
  FastAPI's lifespan handler never runs — this deliberately prevents the
  background GitHub issue poller from starting during tests. If you add
  tests that specifically need the poller, spin up a dedicated fixture
  for that instead of enabling it globally.
"""

import textwrap
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.agent import (
    DiagnosisOutput,
    RemediationOutput,
    TestGenerationOutput,
    PipelineResult,
)

# Fixtures


@pytest.fixture
def sample_pipeline_result() -> PipelineResult:
    """A PipelineResult whose code_fix/test_code are real, runnable Python —
    used by tests that exercise the actual sandbox subprocess."""
    return PipelineResult(
        diagnosis=DiagnosisOutput(
            summary="Division by zero in calculate_rate",
            root_cause_analysis="calculate_rate divides by `total` without guarding against 0.",
            affected_files=["utils/rate.py"],
            risk_score=4,
        ),
        remediation=RemediationOutput(
            patch_explanation="Guard against a zero denominator and return 0.0 instead of raising.",
            target_file="utils/rate.py",
            code_fix=textwrap.dedent("""
                def calculate_rate(successes: int, total: int) -> float:
                    if total == 0:
                        return 0.0
                    return successes / total
            """).strip() + "\n",
            git_diff_patch=(
                "--- a/utils/rate.py\n"
                "+++ b/utils/rate.py\n"
                "@@ -1,2 +1,4 @@\n"
                "-def calculate_rate(successes, total):\n"
                "-    return successes / total\n"
                "+def calculate_rate(successes: int, total: int) -> float:\n"
                "+    if total == 0:\n"
                "+        return 0.0\n"
                "+    return successes / total\n"
            ),
        ),
        test_generation=TestGenerationOutput(
            test_file_name="test_calculate_rate_fix.py",
            test_code=textwrap.dedent("""
                from utils.rate import calculate_rate

                def test_zero_total_returns_zero():
                    assert calculate_rate(5, 0) == 0.0

                def test_normal_rate():
                    assert calculate_rate(1, 2) == 0.5
            """).strip() + "\n",
            test_description="Verifies the zero-denominator guard and a normal case.",
        ),
    )


@pytest.fixture
def broken_pipeline_result(sample_pipeline_result) -> PipelineResult:
    """Same shape, but the 'fix' is still wrong — the sandbox should reject it."""
    pr = sample_pipeline_result.model_copy(deep=True)
    pr.remediation.code_fix = textwrap.dedent("""
        def calculate_rate(successes: int, total: int) -> float:
            return successes / total  # still unguarded
    """).strip() + "\n"
    return pr


FAKE_ISSUES = [
    {
        "number": 42,
        "title": "ZeroDivisionError in calculate_rate",
        "body": "Crashes when total is 0. See utils/rate.py, calculate_rate(...)",
        "created_at": "2026-08-01T00:00:00Z",
        "html_url": "https://github.com/bakiizese/autonomous-ai-sre-platform/issues/42",
    }
]


# Health check


def test_read_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"


# /api/issues


def test_get_issues_success(client, app_module):
    with patch.object(
        app_module.github_client,
        "list_open_issues",
        new=AsyncMock(return_value=FAKE_ISSUES),
    ):
        res = client.get("/api/issues")
    assert res.status_code == 200
    assert res.json() == {"issues": FAKE_ISSUES}


def test_get_issues_upstream_failure_returns_502(client, app_module):
    with patch.object(
        app_module.github_client,
        "list_open_issues",
        new=AsyncMock(side_effect=RuntimeError("GitHub API unreachable")),
    ):
        res = client.get("/api/issues")
    assert res.status_code == 502
    assert "Failed to fetch GitHub issues" in res.json()["detail"]


# /api/triage


def test_triage_success(client, app_module, sample_pipeline_result):
    with patch.object(
        app_module, "run_sre_pipeline", return_value=sample_pipeline_result
    ):
        res = client.post(
            "/api/triage",
            json={
                "error_log": "ZeroDivisionError: division by zero",
                "source_code_context": "def calculate_rate(successes, total): return successes / total",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["diagnosis"]["risk_score"] == 4
    assert body["remediation"]["target_file"] == "utils/rate.py"
    assert body["test_generation"]["test_file_name"] == "test_calculate_rate_fix.py"


def test_triage_engine_failure_returns_500(client, app_module):
    with patch.object(
        app_module, "run_sre_pipeline", side_effect=RuntimeError("Gemini call failed")
    ):
        res = client.post(
            "/api/triage", json={"error_log": "boom", "source_code_context": ""}
        )
    assert res.status_code == 500
    assert "Gemini call failed" in res.json()["detail"]


def test_triage_rejects_missing_fields(client):
    res = client.post(
        "/api/triage", json={"error_log": "boom"}
    )  # missing source_code_context
    assert res.status_code == 422


# /api/verify — real sandbox execution, no mocking


def test_verify_passing_patch_runs_real_sandbox(client, sample_pipeline_result):
    payload = {
        "target_file": sample_pipeline_result.remediation.target_file,
        "remediated_code": sample_pipeline_result.remediation.code_fix,
        "test_file_name": sample_pipeline_result.test_generation.test_file_name,
        "generated_test_code": sample_pipeline_result.test_generation.test_code,
    }
    res = client.post("/api/verify", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] is True
    assert body["target_test_passed"] is True
    assert "2 passed" in body["stdout"]


def test_verify_failing_patch_runs_real_sandbox(client, broken_pipeline_result):
    payload = {
        "target_file": broken_pipeline_result.remediation.target_file,
        "remediated_code": broken_pipeline_result.remediation.code_fix,
        "test_file_name": broken_pipeline_result.test_generation.test_file_name,
        "generated_test_code": broken_pipeline_result.test_generation.test_code,
    }
    res = client.post("/api/verify", json=payload)
    assert res.status_code == 200  # sandbox failure is a *result*, not an HTTP error
    body = res.json()
    assert body["passed"] is False
    assert "1 failed" in body["stdout"] or "ZeroDivisionError" in body["stdout"]


def test_verify_times_out_gracefully(client):
    """A test file that hangs must be killed and reported, not left to block the request forever."""
    payload = {
        "target_file": "slow.py",
        "remediated_code": "def slow():\n    return 1\n",
        "test_file_name": "test_slow.py",
        "generated_test_code": (
            "import time\n"
            "from slow import slow\n\n"
            "def test_never_finishes():\n"
            "    time.sleep(30)\n"
            "    assert slow() == 1\n"
        ),
    }
    # Note: run_preflight_verification's timeout_seconds default (10s) is not
    # exposed on VerificationRequest, so this exercises the endpoint's real
    # default timeout. This test intentionally takes ~10s to run.
    res = client.post("/api/verify", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] is False
    assert "timed out" in body["stderr"].lower()


# /api/remediate-and-pr — the full loop


def test_remediate_and_pr_happy_path(client, app_module, sample_pipeline_result):
    with patch.object(
        app_module, "run_sre_pipeline", return_value=sample_pipeline_result
    ), patch.object(
        app_module.github_client,
        "get_default_branch_sha",
        new=AsyncMock(return_value="deadbeef"),
    ), patch.object(
        app_module.github_client, "create_branch", new=AsyncMock(return_value=True)
    ), patch.object(
        app_module.github_client,
        "create_or_update_file",
        new=AsyncMock(return_value={"commit": {"sha": "abc123"}}),
    ), patch.object(
        app_module.github_client,
        "create_pull_request",
        new=AsyncMock(
            return_value={"html_url": "https://github.com/x/y/pull/7", "number": 7}
        ),
    ), patch.object(
        app_module.github_client,
        "close_issue",
        new=AsyncMock(return_value={"state": "closed"}),
    ):

        res = client.post(
            "/api/remediate-and-pr",
            json={
                "issue_number": 42,
                "error_log": "ZeroDivisionError: division by zero",
                "source_code_context": "def calculate_rate(successes, total): return successes / total",
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["pr_url"] == "https://github.com/x/y/pull/7"
        assert body["pr_number"] == 7
        assert body["branch"] == "fix/issue-42-auto-remediation"
        # This is the real sandbox result, not a mocked stand-in.
        assert body["verification"]["passed"] is True

        app_module.github_client.create_or_update_file.assert_any_await(
            file_path="utils/rate.py",
            content=sample_pipeline_result.remediation.code_fix,
            commit_message="fix: automated patch for issue #42",
            branch_name="fix/issue-42-auto-remediation",
        )
        app_module.github_client.create_pull_request.assert_awaited_once()
        app_module.github_client.close_issue.assert_awaited_once()


def test_remediate_and_pr_blocks_on_failed_sandbox(
    client, app_module, broken_pipeline_result
):
    """A patch that fails its own generated tests must never reach GitHub."""
    with patch.object(
        app_module, "run_sre_pipeline", return_value=broken_pipeline_result
    ), patch.object(
        app_module.github_client, "get_default_branch_sha", new=AsyncMock()
    ) as mock_sha, patch.object(
        app_module.github_client, "create_branch", new=AsyncMock()
    ) as mock_branch, patch.object(
        app_module.github_client, "create_pull_request", new=AsyncMock()
    ) as mock_pr:

        res = client.post(
            "/api/remediate-and-pr",
            json={"issue_number": 99, "error_log": "boom", "source_code_context": ""},
        )

    assert res.status_code == 422
    assert "Pre-flight sandbox checks failed" in res.json()["detail"]
    mock_sha.assert_not_awaited()
    mock_branch.assert_not_awaited()
    mock_pr.assert_not_awaited()


def test_remediate_and_pr_sends_critical_alert_above_threshold(
    client, app_module, sample_pipeline_result
):
    critical = sample_pipeline_result.model_copy(deep=True)
    critical.diagnosis.risk_score = 9  # > CRITICAL_RISK_THRESHOLD (7)

    with patch.object(
        app_module, "run_sre_pipeline", return_value=critical
    ), patch.object(
        app_module.github_client,
        "get_default_branch_sha",
        new=AsyncMock(return_value="sha"),
    ), patch.object(
        app_module.github_client, "create_branch", new=AsyncMock(return_value=True)
    ), patch.object(
        app_module.github_client,
        "create_or_update_file",
        new=AsyncMock(return_value={}),
    ), patch.object(
        app_module.github_client,
        "create_pull_request",
        new=AsyncMock(return_value={"html_url": "u", "number": 1}),
    ), patch.object(
        app_module.github_client, "close_issue", new=AsyncMock(return_value={})
    ), patch.object(
        app_module, "send_critical_alert"
    ) as mock_alert:

        res = client.post(
            "/api/remediate-and-pr",
            json={"issue_number": 7, "error_log": "boom", "source_code_context": ""},
        )

    assert res.status_code == 200
    mock_alert.assert_called_once()
    args = mock_alert.call_args.args
    assert args[0] == 7  # issue number
    assert args[2] == 9  # risk_score


def test_remediate_and_pr_does_not_alert_below_threshold(
    client, app_module, sample_pipeline_result
):
    # sample_pipeline_result has risk_score=4, well under CRITICAL_RISK_THRESHOLD (7)
    with patch.object(
        app_module, "run_sre_pipeline", return_value=sample_pipeline_result
    ), patch.object(
        app_module.github_client,
        "get_default_branch_sha",
        new=AsyncMock(return_value="sha"),
    ), patch.object(
        app_module.github_client, "create_branch", new=AsyncMock(return_value=True)
    ), patch.object(
        app_module.github_client,
        "create_or_update_file",
        new=AsyncMock(return_value={}),
    ), patch.object(
        app_module.github_client,
        "create_pull_request",
        new=AsyncMock(return_value={"html_url": "u", "number": 1}),
    ), patch.object(
        app_module.github_client, "close_issue", new=AsyncMock(return_value={})
    ), patch.object(
        app_module, "send_critical_alert"
    ) as mock_alert:

        res = client.post(
            "/api/remediate-and-pr",
            json={"issue_number": 8, "error_log": "boom", "source_code_context": ""},
        )

    assert res.status_code == 200
    mock_alert.assert_not_called()


# /api/issues/{issue_number}/context


def test_context_resolution_direct_path(client, app_module):
    issue = {"number": 42, "body": "Crash traced to `utils/rate.py`."}
    with patch.object(
        app_module.github_client, "get_issue", new=AsyncMock(return_value=issue)
    ), patch.object(
        app_module.github_client,
        "get_file_content",
        new=AsyncMock(return_value="def calculate_rate(...): ..."),
    ):
        res = client.get("/api/issues/42/context")

    assert res.status_code == 200
    body = res.json()
    assert body["method"] == "direct_path"
    assert body["resolved_path"] == "utils/rate.py"
    assert "calculate_rate" in body["source_code"]


def test_context_resolution_falls_back_to_code_search(client, app_module):
    """No file path in the issue body, but a function name resolves via search_code."""
    issue = {"number": 42, "body": "calculate_rate(5, 0) blows up."}

    async def file_content_side_effect(path):
        return "def calculate_rate(...): ..." if path == "utils/rate.py" else None

    with patch.object(
        app_module.github_client, "get_issue", new=AsyncMock(return_value=issue)
    ), patch.object(
        app_module.github_client,
        "get_file_content",
        new=AsyncMock(side_effect=file_content_side_effect),
    ), patch.object(
        app_module.github_client,
        "search_code",
        new=AsyncMock(return_value=[{"path": "utils/rate.py"}]),
    ) as mock_search:
        res = client.get("/api/issues/42/context")

    assert res.status_code == 200
    body = res.json()
    assert body["method"] == "code_search"
    assert body["resolved_path"] == "utils/rate.py"
    mock_search.assert_awaited_once_with("calculate_rate")


def test_context_resolution_not_found(client, app_module):
    issue = {"number": 42, "body": "Something is broken somewhere, no idea where."}
    with patch.object(
        app_module.github_client, "get_issue", new=AsyncMock(return_value=issue)
    ), patch.object(
        app_module.github_client, "get_file_content", new=AsyncMock(return_value=None)
    ), patch.object(
        app_module.github_client, "search_code", new=AsyncMock(return_value=[])
    ):
        res = client.get("/api/issues/42/context")

    assert res.status_code == 200
    assert res.json() == {
        "source_code": "",
        "resolved_path": None,
        "method": "not_found",
    }


# CORS


def test_cors_allows_configured_frontend_origin(client):
    res = client.options(
        "/api/issues",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in (200, 204)
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
