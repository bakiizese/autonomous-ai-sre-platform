import os
import sys
import tempfile
import subprocess
from app.schemas.agent import VerificationResult

def run_preflight_verification(
    target_file_rel_path: str,
    remediated_code: str,
    test_file_name: str,
    generated_test_code: str,
    timeout_seconds: int = 10
) -> VerificationResult:
    """
    Spawns an isolated temporary directory, writes the remediated code and generated pytest,
    and runs pytest via subprocess.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Determine paths inside sandbox
        target_path = os.path.join(temp_dir, target_file_rel_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        test_path = os.path.join(temp_dir, test_file_name)

        # Write code fix and test file into sandbox
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(remediated_code)

        with open(test_path, "w", encoding="utf-8") as f:
            f.write(generated_test_code)

        # Execute pytest in sandbox
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_path],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            
            passed = (result.returncode == 0)
            return VerificationResult(
                passed=passed,
                target_test_passed=passed,
                stdout=result.stdout,
                stderr=result.stderr
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                target_test_passed=False,
                stdout="",
                stderr=f"Execution timed out after {timeout_seconds} seconds."
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                target_test_passed=False,
                stdout="",
                stderr=str(e)
            )