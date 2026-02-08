import os

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

from events import EventBus
from pipeline import print_banner, run_stage
from test_hooks import create_test_monitor_hook
from test_tracker import TestOutcome, TestResult, TestTracker
from test_verifier import detect_test_command, verify_tests

MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
MAX_GREEN_FIX_ATTEMPTS = int(os.getenv("MAX_GREEN_FIX_ATTEMPTS", "3"))

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template from prompts/<name>.md and format it."""
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        template = f.read()
    return template.format(**kwargs) if kwargs else template


async def _emit(event_bus: EventBus | None, event: dict) -> None:
    if event_bus:
        await event_bus.emit(event)


async def _log(msg: str, event_bus: EventBus | None = None) -> None:
    print(f"  {msg}")
    await _emit(event_bus, {"type": "log", "data": {"message": msg}})


async def _verify_and_emit(
    tracker: TestTracker, target: str, stage: str, event_bus: EventBus | None = None
) -> TestResult:
    """Run independent test verification and emit the result."""
    print_banner(f"{stage} - VERIFY", "Independent test verification")
    result = await verify_tests(tracker, target)
    await _emit(event_bus, {
        "type": "test_verify",
        "data": {
            "stage": stage,
            "outcome": result.outcome.value,
            "exit_code": result.exit_code,
            "total_tests": result.total_tests,
            "failures": result.failures,
            "errors": result.errors,
            "output_tail": result.stdout[-1000:] if result.stdout else "",
        },
    })
    status = "PASS" if result.outcome == TestOutcome.PASS else "FAIL"
    await _log(
        f"Verification: {status} (exit code {result.exit_code}, "
        f"{result.failures} failures, {result.errors} errors)",
        event_bus,
    )
    return result


async def run_pipeline(ticket: str, target: str, event_bus: EventBus | None = None) -> str:
    """Run the full TDD pipeline and return the final report text."""

    print_banner("INIT", "TDD Agent Pipeline")
    await _emit(event_bus, {
        "type": "init",
        "data": {"ticket": ticket[:200], "target": target},
    })
    print(f"  Ticket content:\n  {ticket[:200]}{'...' if len(ticket) > 200 else ''}\n")

    # --- Set up test tracking and hooks ---
    tracker = TestTracker()
    tracker.canonical_test_command = detect_test_command(target)
    test_cmd = tracker.canonical_test_command
    await _log(f"Detected test command: {test_cmd}", event_bus)

    test_monitor_hook = create_test_monitor_hook(tracker)

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        cwd=target,
        max_turns=50,
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Bash", hooks=[test_monitor_hook]),
            ],
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        # ── Stage 1 — PLAN ──
        await run_stage(
            client,
            "STAGE 1 - PLAN",
            "Analyzing ticket and planning approach",
            _load_prompt("plan", ticket=ticket),
            event_bus=event_bus,
        )

        # ── Stage 2 — RED (Write Tests) ──
        await run_stage(
            client,
            "STAGE 2 - RED",
            "Writing tests (TDD - expecting failures)",
            _load_prompt("red", test_cmd=test_cmd),
            event_bus=event_bus,
        )

        # ── Stage 3 — GREEN (Implement) ──
        await run_stage(
            client,
            "STAGE 3 - GREEN",
            "Implementing feature/fix to make tests pass",
            _load_prompt("green", test_cmd=test_cmd),
            event_bus=event_bus,
        )

        # ── Verification gate after GREEN ──
        gate = await _verify_and_emit(tracker, target, "STAGE 3", event_bus)

        if gate.outcome != TestOutcome.PASS:
            for fix_attempt in range(1, MAX_GREEN_FIX_ATTEMPTS + 1):
                await run_stage(
                    client,
                    f"STAGE 3 - GREEN (fix attempt {fix_attempt}/{MAX_GREEN_FIX_ATTEMPTS})",
                    "Fixing failing tests based on actual test output",
                    _load_prompt(
                        "green_fix",
                        gate_command=gate.command,
                        gate_exit_code=str(gate.exit_code),
                        gate_failures=str(gate.failures),
                        gate_errors=str(gate.errors),
                        gate_stdout=gate.stdout[-3000:],
                        gate_stderr=gate.stderr[-1000:],
                        test_cmd=test_cmd,
                    ),
                    event_bus=event_bus,
                )
                gate = await _verify_and_emit(tracker, target, f"STAGE 3 fix {fix_attempt}", event_bus)
                if gate.outcome == TestOutcome.PASS:
                    break
            else:
                await _log(
                    f"WARNING: Tests still failing after {MAX_GREEN_FIX_ATTEMPTS} fix attempts",
                    event_bus,
                )

        # ── Stage 4 — REVIEW loop ──
        for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
            # Run independent verification before each review
            verify_result = await _verify_and_emit(tracker, target, f"STAGE 4 round {iteration}", event_bus)

            test_status_block = (
                f"ACTUAL TEST STATUS (from independent pipeline verification):\n"
                f"  Command: {verify_result.command}\n"
                f"  Exit code: {verify_result.exit_code}\n"
                f"  Outcome: {verify_result.outcome.value}\n"
                f"  Tests: {verify_result.total_tests}, "
                f"Failures: {verify_result.failures}, Errors: {verify_result.errors}\n"
            )
            if verify_result.outcome != TestOutcome.PASS:
                test_status_block += (
                    f"  Output (tail):\n```\n{verify_result.stdout[-2000:]}\n```\n"
                )

            review = await run_stage(
                client,
                f"STAGE 4 - REVIEW (round {iteration}/{MAX_REVIEW_ITERATIONS})",
                "Reviewing implementation",
                _load_prompt("review", test_status_block=test_status_block),
                event_bus=event_bus,
            )

            # Override APPROVED if tests are actually failing
            if "VERDICT: APPROVED" in review and verify_result.outcome != TestOutcome.PASS:
                override_msg = (
                    f"OVERRIDE: Agent said APPROVED but tests are actually FAILING "
                    f"(exit code {verify_result.exit_code}, {verify_result.failures} failures). "
                    f"Treating as CHANGES_NEEDED."
                )
                await _log(override_msg, event_bus)
                review = review.replace("VERDICT: APPROVED", "VERDICT: CHANGES_NEEDED (OVERRIDDEN)")

            if "VERDICT: APPROVED" in review:
                await _log(f"Review APPROVED on round {iteration}", event_bus)
                break

            await _log(f"Reviewer found issues on round {iteration}, looping back...", event_bus)

            # RED — write tests for the issues found
            await run_stage(
                client,
                f"STAGE 4.{iteration} - RED (fix)",
                "Writing tests for reviewer findings",
                _load_prompt("review_red", test_cmd=test_cmd),
                event_bus=event_bus,
            )

            # GREEN — fix the issues
            await run_stage(
                client,
                f"STAGE 4.{iteration} - GREEN (fix)",
                "Fixing reviewer findings",
                _load_prompt("review_green", test_cmd=test_cmd),
                event_bus=event_bus,
            )

            # Verify after each fix round
            fix_gate = await _verify_and_emit(tracker, target, f"STAGE 4.{iteration} fix", event_bus)
            if fix_gate.outcome != TestOutcome.PASS:
                await _log(
                    f"Tests still failing after review fix round {iteration}: "
                    f"{fix_gate.failures} failures, {fix_gate.errors} errors",
                    event_bus,
                )
        else:
            await _log(
                f"Review did not approve after {MAX_REVIEW_ITERATIONS} rounds — proceeding to report.",
                event_bus,
            )

        # ── Final verification before report ──
        final_verify = await _verify_and_emit(tracker, target, "FINAL", event_bus)

        # ── Stage 5 — REPORT ──
        final_test_block = (
            f"FINAL TEST VERIFICATION (authoritative):\n"
            f"  Command: {final_verify.command}\n"
            f"  Exit code: {final_verify.exit_code}\n"
            f"  Outcome: {final_verify.outcome.value}\n"
            f"  Tests: {final_verify.total_tests}, "
            f"Failures: {final_verify.failures}, Errors: {final_verify.errors}\n"
        )
        if final_verify.stdout:
            final_test_block += f"  Output:\n```\n{final_verify.stdout[-2000:]}\n```\n"

        report = await run_stage(
            client,
            "STAGE 5 - REPORT",
            "Generating final TDD report",
            _load_prompt("report", final_test_block=final_test_block),
            event_bus=event_bus,
        )

    return report
