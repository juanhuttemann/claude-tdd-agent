import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum


class TestOutcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class TestResult:
    """Result of a single test run."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    outcome: TestOutcome
    total_tests: int = 0
    failures: int = 0
    errors: int = 0
    timestamp: float = 0.0


# Patterns that identify a command as a test invocation
_TEST_COMMAND_PATTERNS: list[str] = [
    r"\bbin/rails\s+test\b",
    r"\bpytest\b",
    r"\bnpm\s+test\b",
    r"\byarn\s+test\b",
    r"\bgo\s+test\b",
    r"\bcargo\s+test\b",
    r"\brspec\b",
    r"\bphpunit\b",
    r"\bjest\b",
    r"\bmocha\b",
    r"\bruby\s+-Itest\b",
    r"\bruby\s+-Ilib\b",
]


def is_test_command(command: str) -> bool:
    """Check if a shell command looks like a test invocation."""
    return any(re.search(p, command) for p in _TEST_COMMAND_PATTERNS)


def parse_test_counts(result: TestResult, output: str) -> None:
    """Extract test/failure/error counts from common test runner output."""
    # Rails/minitest: "33 runs, 45 assertions, 2 failures, 0 errors, 0 skips"
    m = re.search(r"(\d+)\s+runs?.*?(\d+)\s+failures?.*?(\d+)\s+errors?", output)
    if m:
        result.total_tests = int(m.group(1))
        result.failures = int(m.group(2))
        result.errors = int(m.group(3))
        return
    # pytest: "5 passed, 2 failed"
    passed = re.search(r"(\d+)\s+passed", output)
    failed = re.search(r"(\d+)\s+failed", output)
    if passed or failed:
        result.total_tests = int(passed.group(1)) if passed else 0
        f = int(failed.group(1)) if failed else 0
        result.failures = f
        result.total_tests += f
        return
    # jest/mocha: "Tests: 2 failed, 5 passed, 7 total"
    m = re.search(r"Tests:\s+(\d+)\s+failed.*?(\d+)\s+total", output)
    if m:
        result.failures = int(m.group(1))
        result.total_tests = int(m.group(2))


@dataclass
class TestTracker:
    """Shared state tracking test results across the pipeline."""
    results: list[TestResult] = field(default_factory=list)
    canonical_test_command: str = "bin/rails test"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def record(self, result: TestResult) -> None:
        async with self._lock:
            self.results.append(result)

    @property
    def last_result(self) -> TestResult | None:
        return self.results[-1] if self.results else None

    @property
    def all_passing(self) -> bool:
        r = self.last_result
        return r is not None and r.outcome == TestOutcome.PASS

    def summary(self) -> str:
        """Human-readable summary of the latest test result."""
        r = self.last_result
        if r is None:
            return "No test results recorded."
        if r.outcome == TestOutcome.PASS:
            return f"PASS: {r.total_tests} tests, 0 failures (exit code {r.exit_code})"
        lines = [
            f"FAIL: {r.total_tests} tests, {r.failures} failures, "
            f"{r.errors} errors (exit code {r.exit_code})",
        ]
        if r.stdout:
            lines.append(f"Output (last 2000 chars):\n{r.stdout[-2000:]}")
        if r.stderr:
            lines.append(f"Stderr (last 500 chars):\n{r.stderr[-500:]}")
        return "\n".join(lines)
