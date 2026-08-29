import json
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.agent import (
    DiagnosisOutput,
    PipelineResult,
    RemediationOutput,
    TestGenerationOutput,
)

from app.services.agent_engine import MODEL_ID, run_sre_pipeline


@pytest.fixture
def mock_pipeline_result():
    """Provides a valid sample PipelineResult instance and its JSON string representation."""
    data = PipelineResult(
        diagnosis=DiagnosisOutput(
            root_cause="Null Pointer Exception in process_data",
            risk_score=7,
        ),
        remediation=RemediationOutput(
            code_fix="def process_data(data):\n    if not data: return None",
            git_diff="--- a/main.py\n+++ b/main.py\n@@ -1,1 +1,2 @@",
        ),
        test_generation=TestGenerationOutput(
            pytest_code="def test_process_data():\n    assert process_data(None) is None"
        ),
    )
    return data, data.model_dump_json()


@pytest.fixture
def sample_inputs():
    """Provides sample error logs and source code context."""
    return {
        "error_log": "TypeError: 'NoneType' object is not iterable",
        "source_code_context": "def process_data(data):\n    for item in data:\n        print(item)",
    }


@patch("app.sre_pipeline.client")
def test_run_sre_pipeline_success(mock_client, sample_inputs, mock_pipeline_result):
    """Test successful response parsing from the Gemini API call."""
    expected_result_obj, json_response = mock_pipeline_result

    # Mock response object from client.models.generate_content
    mock_response = MagicMock()
    mock_response.text = json_response
    mock_client.models.generate_content.return_value = mock_response

    # Execute pipeline function
    result = run_sre_pipeline(
        error_log=sample_inputs["error_log"],
        source_code_context=sample_inputs["source_code_context"],
    )

    # Assertions on returned structured object
    assert isinstance(result, PipelineResult)
    assert result.diagnosis.risk_score == 7
    assert "Null Pointer Exception" in result.diagnosis.root_cause
    assert result == expected_result_obj

    # Verify Gemini API client call parameters
    mock_client.models.generate_content.assert_called_once()
    call_args, call_kwargs = mock_client.models.generate_content.call_args

    assert call_kwargs["model"] == MODEL_ID
    assert sample_inputs["error_log"] in call_kwargs["contents"]
    assert sample_inputs["source_code_context"] in call_kwargs["contents"]

    config = call_kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema == PipelineResult
    assert config.temperature == 0.2


@patch("app.sre_pipeline.client")
def test_run_sre_pipeline_invalid_json(mock_client, sample_inputs):
    """Test handling when the LLM returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.text = "invalid json string"
    mock_client.models.generate_content.return_value = mock_response

    with pytest.raises(Exception):
        run_sre_pipeline(
            error_log=sample_inputs["error_log"],
            source_code_context=sample_inputs["source_code_context"],
        )


@patch("app.sre_pipeline.client")
def test_run_sre_pipeline_api_error(mock_client, sample_inputs):
    """Test exception propagation when Gemini API raises an error."""
    mock_client.models.generate_content.side_effect = Exception("API Quota Exceeded")

    with pytest.raises(Exception) as exc_info:
        run_sre_pipeline(
            error_log=sample_inputs["error_log"],
            source_code_context=sample_inputs["source_code_context"],
        )

    assert "API Quota Exceeded" in str(exc_info.value)
