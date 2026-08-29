import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.agent import VerificationResult

from app.services.sandbox_runner import run_preflight_verification


@pytest.fixture
def sample_verification_args():
    return {
        "target_file_rel_path": "app/utils.py",
        "remediated_code": "def add(a, b):\n    return a + b\n",
        "test_file_name": "test_utils.py",
        "generated_test_code": "from app.utils import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        "timeout_seconds": 5,
    }


@patch("subprocess.run")
def test_preflight_verification_passing_tests(
    mock_subprocess_run, sample_verification_args
):
    """Test successful pytest execution where returncode is 0."""
    mock_subprocess_run.return_value = MagicMock(
        returncode=0,
        stdout="1 passed in 0.01s",
        stderr="",
    )

    result = run_preflight_verification(**sample_verification_args)

    assert isinstance(result, VerificationResult)
    assert result.passed is True
    assert result.target_test_passed is True
    assert result.stdout == "1 passed in 0.01s"
    assert result.stderr == ""

    # Verify subprocess call parameters
    mock_subprocess_run.assert_called_once()
    call_args, call_kwargs = mock_subprocess_run.call_args
    assert call_kwargs["timeout"] == 5
    assert call_kwargs["capture_output"] is True
    assert call_kwargs["text"] is True


@patch("subprocess.run")
def test_preflight_verification_failing_tests(
    mock_subprocess_run, sample_verification_args
):
    """Test pytest execution failure where returncode is non-zero."""
    mock_subprocess_run.return_value = MagicMock(
        returncode=1,
        stdout="1 failed in 0.02s",
        stderr="AssertionError: assert 3 == 4",
    )

    result = run_preflight_verification(**sample_verification_args)

    assert result.passed is False
    assert result.target_test_passed is False
    assert result.stdout == "1 failed in 0.02s"
    assert "AssertionError" in result.stderr


@patch("subprocess.run")
def test_preflight_verification_timeout(mock_subprocess_run, sample_verification_args):
    """Test subprocess timeout exception handling."""
    mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=5)

    result = run_preflight_verification(**sample_verification_args)

    assert result.passed is False
    assert result.target_test_passed is False
    assert result.stdout == ""
    assert "Execution timed out after 5 seconds." in result.stderr


@patch("subprocess.run")
def test_preflight_verification_generic_exception(
    mock_subprocess_run, sample_verification_args
):
    """Test handling of unexpected process errors (e.g., executable not found)."""
    mock_subprocess_run.side_effect = Exception("OS Error: Failed to execute process")

    result = run_preflight_verification(**sample_verification_args)

    assert result.passed is False
    assert result.target_test_passed is False
    assert result.stdout == ""
    assert "OS Error: Failed to execute process" in result.stderr


def test_preflight_verification_file_creation(sample_verification_args):
    """Integrations test: verify files are correctly written inside temp_dir during execution."""
    recorded_temp_dir = None

    def fake_subprocess_run(cmd, cwd, **kwargs):
        nonlocal recorded_temp_dir
        recorded_temp_dir = cwd

        target_full_path = os.path.join(
            cwd, sample_verification_args["target_file_rel_path"]
        )
        test_full_path = os.path.join(cwd, sample_verification_args["test_file_name"])

        # Check target file was written correctly
        assert os.path.exists(target_full_path)
        with open(target_full_path, "r", encoding="utf-8") as f:
            assert f.read() == sample_verification_args["remediated_code"]

        # Check test file was written correctly
        assert os.path.exists(test_full_path)
        with open(test_full_path, "r", encoding="utf-8") as f:
            assert f.read() == sample_verification_args["generated_test_code"]

        return MagicMock(returncode=0, stdout="OK", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        run_preflight_verification(**sample_verification_args)

    # Confirm temporary directory was cleaned up after exiting context
    assert recorded_temp_dir is not None
    assert not os.path.exists(recorded_temp_dir)
