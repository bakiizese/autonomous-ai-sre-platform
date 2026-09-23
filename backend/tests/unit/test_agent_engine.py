from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors

from app.schemas.agent import (
    DiagnosisOutput,
    RemediationOutput,
    TestGenerationOutput,
    VerificationResult,
)
from app.services import agent_engine


def _mock_response(payload_model) -> MagicMock:
    resp = MagicMock()
    resp.text = payload_model.model_dump_json()
    return resp


@pytest.fixture
def mock_diagnosis():
    return DiagnosisOutput(
        summary="Null payload not handled.",
        root_cause_analysis="process_data() doesn't guard against None.",
        affected_files=["app/services/data.py"],
        risk_score=9,
    )


@pytest.fixture
def mock_remediation():
    return RemediationOutput(
        patch_explanation="Guard against None before iterating.",
        target_file="app/services/data.py",
        code_fix="def process_data(data):\n    if not data:\n        return\n",
        git_diff_patch="--- a/app/services/data.py\n+++ b/app/services/data.py",
    )


@pytest.fixture
def mock_test_generation():
    return TestGenerationOutput(
        test_file_name="test_process_data.py",
        test_code="def test_process_data_none():\n    assert True\n",
        test_description="Verifies None input no longer raises.",
    )


@pytest.fixture(autouse=True)
def isolate_rate_limit_state():
    """These tests exercise the real rate_limit_service (backed by Postgres,
    same as the rest of the suite) — clear it before/after so a limited state
    left by one test can't leak into another."""
    from app.db.models import RateLimitState
    from app.services.rate_limit_service import SessionLocal

    def _clear():
        with SessionLocal() as session:
            session.query(RateLimitState).delete()
            session.commit()

    _clear()
    yield
    _clear()


# ---------------------------------------------------------------------------
# Node-level tests
# ---------------------------------------------------------------------------


def test_diagnose_node_calls_gemini_with_diagnosis_schema(mock_diagnosis):
    with patch.object(agent_engine, "client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_response(mock_diagnosis)

        result = agent_engine.diagnose_node({"error_log": "boom", "source_code_context": "", "node_trace": []})

        assert result["diagnosis"].risk_score == 9
        assert result["node_trace"][0]["node"] == "diagnose"
        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs["config"].response_schema is DiagnosisOutput


def test_fix_node_increments_fix_attempt_and_includes_prior_failure(mock_diagnosis, mock_remediation):
    with patch.object(agent_engine, "client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_response(mock_remediation)

        prior_verification = VerificationResult(
            passed=False, target_test_passed=False, stdout="", stderr="AssertionError: still broken"
        )
        state = {
            "error_log": "boom",
            "source_code_context": "",
            "diagnosis": mock_diagnosis,
            "verification": prior_verification,
            "fix_attempt": 1,
            "node_trace": [],
        }

        result = agent_engine.fix_node(state)

        assert result["fix_attempt"] == 2
        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "PREVIOUS FIX ATTEMPT FAILED" in prompt
        assert "still broken" in prompt


def test_test_gen_node_calls_gemini_with_test_schema(mock_remediation, mock_test_generation):
    with patch.object(agent_engine, "client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_response(mock_test_generation)

        state = {"error_log": "boom", "remediation": mock_remediation, "node_trace": []}
        result = agent_engine.test_gen_node(state)

        assert result["test_generation"].test_file_name == "test_process_data.py"
        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs["config"].response_schema is TestGenerationOutput


def test_verify_node_delegates_to_sandbox_runner(mock_remediation, mock_test_generation):
    passing = VerificationResult(passed=True, target_test_passed=True, stdout="1 passed", stderr="")
    with patch.object(agent_engine, "run_preflight_verification", return_value=passing) as mock_verify:
        state = {
            "remediation": mock_remediation,
            "test_generation": mock_test_generation,
            "node_trace": [],
        }
        result = agent_engine.verify_node(state)

        assert result["verification"].passed is True
        mock_verify.assert_called_once_with(
            target_file_rel_path=mock_remediation.target_file,
            remediated_code=mock_remediation.code_fix,
            test_file_name=mock_test_generation.test_file_name,
            generated_test_code=mock_test_generation.test_code,
        )


# ---------------------------------------------------------------------------
# Full-graph behavior
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_calls(mock_diagnosis, mock_remediation, mock_test_generation):
    responses = {
        DiagnosisOutput: mock_diagnosis.model_dump_json(),
        RemediationOutput: mock_remediation.model_dump_json(),
        TestGenerationOutput: mock_test_generation.model_dump_json(),
    }

    def fake_generate_content(model, contents, config):
        resp = MagicMock()
        resp.text = responses[config.response_schema]
        return resp

    with patch.object(agent_engine, "client") as mock_client:
        mock_client.models.generate_content.side_effect = fake_generate_content
        yield mock_client


def test_stop_after_diagnosis_short_circuits(mock_llm_calls):
    with patch.object(agent_engine, "run_preflight_verification") as mock_verify:
        state = agent_engine.run_sre_pipeline("boom", "", stop_after_diagnosis=True)

        assert "diagnosis" in state
        assert "remediation" not in state
        assert "verification" not in state
        mock_verify.assert_not_called()


def test_verify_failure_triggers_one_retry_then_succeeds(mock_llm_calls):
    outcomes = iter(
        [
            VerificationResult(passed=False, target_test_passed=False, stdout="", stderr="boom"),
            VerificationResult(passed=True, target_test_passed=True, stdout="ok", stderr=""),
        ]
    )
    with patch.object(agent_engine, "run_preflight_verification", side_effect=lambda **_: next(outcomes)):
        state = agent_engine.run_sre_pipeline("boom", "", max_fix_attempts=1)

        assert state["verification"].passed is True
        assert state["fix_attempt"] == 2
        assert [t["node"] for t in state["node_trace"]] == [
            "diagnose", "fix", "test_gen", "verify", "fix", "test_gen", "verify",
        ]


def test_gives_up_after_exhausting_retries(mock_llm_calls):
    failing = VerificationResult(passed=False, target_test_passed=False, stdout="", stderr="still broken")
    with patch.object(agent_engine, "run_preflight_verification", return_value=failing):
        state = agent_engine.run_sre_pipeline("boom", "", max_fix_attempts=1)

        assert state["verification"].passed is False
        assert state["fix_attempt"] == 2  # 1 original attempt + 1 retry, then it stops
        assert len([t for t in state["node_trace"] if t["node"] == "fix"]) == 2


def test_fails_fast_when_already_rate_limited():
    with patch.object(agent_engine, "client") as mock_client, patch(
        "app.services.rate_limit_service.is_gemini_limited", return_value=True
    ):
        with pytest.raises(agent_engine.GeminiStillRateLimitedError):
            agent_engine.run_sre_pipeline("boom", "", stop_after_diagnosis=True)

        mock_client.models.generate_content.assert_not_called()


def test_recovers_from_429_via_automatic_node_retry(mock_diagnosis):
    call_count = {"n": 0}

    def flaky(model, contents, config):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise errors.ClientError(429, {"error": {"message": "rate limited"}})
        resp = MagicMock()
        resp.text = mock_diagnosis.model_dump_json()
        return resp

    with patch.object(agent_engine, "client") as mock_client:
        mock_client.models.generate_content.side_effect = flaky

        state = agent_engine.run_sre_pipeline("boom", "", stop_after_diagnosis=True)

        assert call_count["n"] == 2
        assert state["diagnosis"].risk_score == 9

        from app.services import rate_limit_service

        status = rate_limit_service.get_status()
        # the node retried and eventually succeeded, so the final recorded
        # state is a successful call, not a still-limited one
        assert status["gemini"]["is_limited"] is False


def test_to_pipeline_result_reassembles_old_shape(mock_llm_calls):
    with patch.object(agent_engine, "run_preflight_verification") as mock_verify:
        from app.schemas.agent import VerificationResult as VR

        mock_verify.return_value = VR(passed=True, target_test_passed=True, stdout="ok", stderr="")
        state = agent_engine.run_sre_pipeline("boom", "")

        result = agent_engine.to_pipeline_result(state)

        assert result.diagnosis.risk_score == state["diagnosis"].risk_score
        assert result.remediation.target_file == state["remediation"].target_file
        assert result.test_generation.test_file_name == state["test_generation"].test_file_name
