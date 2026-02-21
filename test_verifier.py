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


def detect_test_command(target: str) -> str | None:
    """Auto-detect the test framework based on project files.

    Returns None if the project type cannot be determined yet (e.g. empty directory).
    Callers should re-run detection after the PLAN stage creates project files.
    """
    def exists(*parts: str) -> bool:
        return os.path.exists(os.path.join(target, *parts))

    # Ruby / Rails
    if exists("bin", "rails"):
        return "bin/rails test"
    if exists("Gemfile") and exists("spec"):
        return "bundle exec rspec"
    if exists("Gemfile") and exists("test"):
        return "bundle exec rake test"

    # Python
    if exists("pytest.ini") or exists("setup.cfg") or exists("pyproject.toml"):
        return "python -m pytest"
    if exists("manage.py"):                      # Django
        return "python manage.py test"
    if exists("setup.py") or exists("tox.ini"):
        return "python -m pytest"

    # PHP
    if exists("vendor", "bin", "phpunit"):
        return "vendor/bin/phpunit"
    if exists("phpunit.xml") or exists("phpunit.xml.dist"):
        return "vendor/bin/phpunit"
    if exists("composer.json"):
        return "vendor/bin/phpunit"

    # JavaScript / TypeScript
    if exists("package.json"):
        if exists("node_modules", ".bin", "jest"):
            return "npx jest"
        if exists("node_modules", ".bin", "vitest"):
            return "npx vitest run"
        return "npm test"

    # Go
    if exists("go.mod"):
        return "go test ./..."

    # Rust
    if exists("Cargo.toml"):
        return "cargo test"

    # Java
    if exists("pom.xml"):
        return "mvn test"
    if exists("build.gradle") or exists("build.gradle.kts"):
        return "./gradlew test"

    # .NET
    if exists("*.sln") or exists("*.csproj"):
        return "dotnet test"

    # Elixir
    if exists("mix.exs"):
        return "mix test"

    # Swift
    if exists("Package.swift"):
        return "swift test"

    return None
