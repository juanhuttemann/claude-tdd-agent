"""Independent out-of-band test verification via subprocess.

This is the authoritative source of truth for whether tests pass.
The pipeline uses these results to gate stage transitions — the agent's
textual claims about test status are irrelevant compared to this.
"""

import asyncio
import os
import time

from test_tracker import TestOutcome, TestResult, TestTracker, parse_test_counts


async def verify_tests(
    tracker: TestTracker,
    cwd: str,
    timeout: int = 120,
) -> TestResult:
    """Run tests via subprocess and return the actual result.

    This runs independently of the agent session and captures the real
    exit code and output.
    """
    command = tracker.canonical_test_command

    proc = None
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode or 0

    except asyncio.TimeoutError:
        if proc:
            proc.kill()
        return TestResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr="Test verification timed out",
            outcome=TestOutcome.ERROR,
            timestamp=time.time(),
        )
    except Exception as e:
        return TestResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            outcome=TestOutcome.ERROR,
            timestamp=time.time(),
        )

    outcome = TestOutcome.PASS if exit_code == 0 else TestOutcome.FAIL
    result = TestResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        outcome=outcome,
        timestamp=time.time(),
    )
    parse_test_counts(result, stdout)

    await tracker.record(result)
    return result


def detect_test_command(target: str) -> str:
    """Auto-detect the test framework based on project files."""
    if os.path.exists(os.path.join(target, "bin", "rails")):
        return "bin/rails test"
    if os.path.exists(os.path.join(target, "Gemfile")) and os.path.exists(
        os.path.join(target, "spec")
    ):
        return "bundle exec rspec"
    if os.path.exists(os.path.join(target, "pytest.ini")) or os.path.exists(
        os.path.join(target, "setup.cfg")
    ):
        return "python -m pytest"
    if os.path.exists(os.path.join(target, "pyproject.toml")):
        return "python -m pytest"
    if os.path.exists(os.path.join(target, "package.json")):
        return "npm test"
    if os.path.exists(os.path.join(target, "Cargo.toml")):
        return "cargo test"
    if os.path.exists(os.path.join(target, "go.mod")):
        return "go test ./..."
    # Default fallback
    return "bin/rails test"
