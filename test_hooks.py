"""PostToolUse hook that monitors Bash test commands and injects corrective context."""

import re
import time
from typing import Any

from test_tracker import (
    TestOutcome,
    TestResult,
    TestTracker,
    is_test_command,
    parse_test_counts,
)


def create_test_monitor_hook(tracker: TestTracker):
    """Return a PostToolUse callback bound to the given tracker.

    When the agent runs a test command via Bash, this hook:
    1. Extracts the exit code and output from tool_response
    2. Records the result in the tracker
    3. If tests failed, injects strong corrective context so the agent
       cannot claim failures are "intentional"
    """

    async def hook(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        command = input_data.get("tool_input", {}).get("command", "")
        if not is_test_command(command):
            return {}

        tool_response = input_data.get("tool_response", "")

        # tool_response may be a dict with {output, exitCode} or a string
        if isinstance(tool_response, dict):
            output_text = str(tool_response.get("output", ""))
            exit_code = int(tool_response.get("exitCode", 0))
        else:
            output_text = str(tool_response) if tool_response else ""
            # Infer exit code from output content
            exit_code = _infer_exit_code(output_text)

        outcome = TestOutcome.PASS if exit_code == 0 else TestOutcome.FAIL

        result = TestResult(
            command=command,
            exit_code=exit_code,
            stdout=output_text,
            stderr="",
            outcome=outcome,
            timestamp=time.time(),
        )
        parse_test_counts(result, output_text)

        # If exit code says pass but output shows failures, override
        if outcome == TestOutcome.PASS and result.failures > 0:
            result.outcome = TestOutcome.FAIL

        await tracker.record(result)

        if result.outcome == TestOutcome.FAIL:
            # Detect if the agent is stuck in a loop with the same failure count
            # Exclude the result we just appended (last element)
            recent = tracker.results[-6:-1]
            consecutive_same = 0
            for prev in reversed(recent):
                if (
                    prev.outcome == TestOutcome.FAIL
                    and prev.failures == result.failures
                    and prev.errors == result.errors
                ):
                    consecutive_same += 1
                else:
                    break

            context_msg = (
                "[PIPELINE MONITOR] TESTS FAILED (exit code "
                f"{exit_code}, {result.failures} failures, "
                f"{result.errors} errors). "
                "These failures are REAL bugs, NOT intentional. "
                "You MUST fix the implementation to make ALL tests "
                "pass. Do NOT claim any failures are expected or "
                "intentional. Do NOT proceed until all tests pass."
            )

            if consecutive_same >= 3:
                # Include the actual test output so the agent has the
                # information it needs without having to re-run tests.
                output_tail = output_text[-2000:] if output_text else "(no output)"
                context_msg += (
                    f" WARNING: Same failure count for the last "
                    f"{consecutive_same} consecutive runs — you are stuck in a loop.\n"
                    "MANDATORY RECOVERY STEPS:\n"
                    "  1. STOP. Do not run the tests again yet.\n"
                    "  2. Use the Read tool to open the test file directly.\n"
                    "  3. Find the exact assertion that is failing.\n"
                    "  4. Ask yourself: what must my implementation return/do to "
                    "satisfy that specific assertion?\n"
                    "  5. Make only that one targeted change, then re-run.\n"
                    "If the pipeline blocks you from editing a test file, that is "
                    "correct — it means you must change the IMPLEMENTATION, not the test.\n"
                    f"Last test output (for reference):\n```\n{output_tail}\n```"
                )

            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context_msg,
                }
            }

        return {}

    return hook


def _infer_exit_code(output: str) -> int:
    """Best-effort exit code inference when not available directly."""
    # Check for minitest failure pattern
    m = re.search(r"(\d+)\s+failures?,\s*(\d+)\s+errors?", output)
    if m and (int(m.group(1)) > 0 or int(m.group(2)) > 0):
        return 1
    # Check for explicit failure markers
    if re.search(r"\bFAILED\b|\bFail(?:ure|ed)\b", output):
        return 1
    return 0
