import os
import sys
import tempfile
import subprocess
from app.schemas.agent import VerificationResult

# `nobody` — what the sandboxed pytest drops to when the server runs as root
# (the Docker default), so it can't read the server's /proc/<pid>/environ.
_UNPRIVILEGED_ID = 65534

# Runs inside the sandbox process before pytest: caps CPU time, memory, file
# size and (when already unprivileged) process count. Done in a bootstrap
# instead of subprocess's preexec_fn, which isn't safe from a thread pool.
_BOOTSTRAP = """
import os, resource, sys
cpu = int(sys.argv[2])
resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
resource.setrlimit(resource.RLIMIT_FSIZE, (10 << 20, 10 << 20))
if os.geteuid() == %d:
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
import pytest
sys.exit(pytest.main([sys.argv[1], "-p", "no:cacheprovider"]))
""" % _UNPRIVILEGED_ID


def _sandbox_env(temp_dir: str) -> dict:
    """Generated code is untrusted (its content can be steered by whoever opens
    an issue), so it never inherits the server's environment — that's where
    GITHUB_TOKEN, GEMINI_API_KEY and SMTP_PASSWORD live."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": temp_dir,
        "TMPDIR": temp_dir,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }


def run_preflight_verification(
    target_file_rel_path: str,
    remediated_code: str,
    test_file_name: str,
    generated_test_code: str,
    timeout_seconds: int = 10
) -> VerificationResult:
    """
    Spawns an isolated temporary directory, writes the remediated code and generated pytest,
    and runs pytest via subprocess with a scrubbed environment, resource limits, and — when
    the server is root — as an unprivileged user.

    This is process-level isolation, not a container: it does not block network access.
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

        run_as: dict = {}
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            run_as = {"user": _UNPRIVILEGED_ID, "group": _UNPRIVILEGED_ID}
            for root, dirs, files in os.walk(temp_dir):
                for name in [root, *[os.path.join(root, n) for n in dirs + files]]:
                    os.chown(name, _UNPRIVILEGED_ID, _UNPRIVILEGED_ID)

        # Execute pytest in sandbox
        try:
            result = subprocess.run(
                [sys.executable, "-c", _BOOTSTRAP, test_path, str(int(timeout_seconds) + 5)],
                cwd=temp_dir,
                env=_sandbox_env(temp_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                **run_as,
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
