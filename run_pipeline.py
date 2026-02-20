import asyncio
import os
import re

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

from events import EventBus
from pipeline import print_banner, run_stage
from test_hooks import create_test_monitor_hook
from test_tracker import TestOutcome, TestResult, TestTracker
from test_verifier import detect_test_command, verify_tests

_BLOCKED_BASH_PATTERNS = [
    r"rm\s+-r[fd]?\s+/(?!\S)",  # rm -rf / (but not rm -rf /some/path)
    r"git\s+push",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-[fd]",
    r"mkfs\b",
    r"dd\s+.*of=/dev/",
    r":\(\)\{.*\}",             # fork bomb
    r"sudo\s+",
    r"chmod\s+-R\s+777\s+/",
    r"drop\s+(table|database)\b",
    r"truncate\s+table\b",
]

_TEST_FILE_PATTERNS = [
    r"(^|/)tests?/",            # test/ or tests/ directory
    r"(^|/)spec/",              # spec/ directory (rspec)
    r"_test\.\w+$",             # _test.go, _test.py, etc.
    r"_spec\.\w+$",             # _spec.rb, _spec.ts, etc.
    r"\.test\.\w+$",            # .test.js, .test.ts, etc.
    r"\.spec\.\w+$",            # .spec.js, .spec.ts, etc.
    r"test_[^/]+\.py$",         # test_*.py (pytest convention)
]


def _is_test_file(file_path: str) -> bool:
    return any(re.search(p, file_path) for p in _TEST_FILE_PATTERNS)


class PipelineStopped(Exception):
    """Raised when the pipeline is stopped by the user between stages."""

    def __init__(
        self,
        completed_stages: list[str],
        current_stage: str,
        tracker: TestTracker,
        session_id: str | None = None,
    ) -> None:
        self.completed_stages = completed_stages
        self.current_stage = current_stage
        self.tracker = tracker
        self.session_id = session_id
        super().__init__(f"Pipeline stopped during {current_stage}")

MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
MAX_GREEN_FIX_ATTEMPTS = int(os.getenv("MAX_GREEN_FIX_ATTEMPTS", "3"))
MAX_SECURITY_ITERATIONS = int(os.getenv("MAX_SECURITY_ITERATIONS", "2"))
MAX_QA_ITERATIONS = int(os.getenv("MAX_QA_ITERATIONS", "2"))

# Model for the main pipeline session (PLAN → RED → GREEN → CODE REVIEW → SECURITY REVIEW)
PIPELINE_MODEL = os.getenv("PIPELINE_MODEL") or None
# Model for the security review stage (defaults to pipeline model)
SECURITY_MODEL = os.getenv("SECURITY_MODEL") or None
# Model for the QA stage (defaults to pipeline model)
QA_MODEL = os.getenv("QA_MODEL") or None
# Cheaper model for the report stage (formatting only)
REPORT_MODEL = os.getenv("REPORT_MODEL", "haiku") or None

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(name: str, target: str | None = None, **kwargs: str) -> str:
    """Load a prompt template from prompts/<name>.md and format it."""
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        template = f.read()
    content = template.format(**kwargs) if kwargs else template
    if target:
        preamble = (
            f"PROJECT DIRECTORY: {target}\n"
            f"You are working exclusively within this directory. All file reads, writes, "
            f"edits, searches, and shell commands MUST operate within {target} only. "
            f"Do NOT access, scan, or create files outside of {target}.\n\n"
        )
        content = preamble + content
    return content


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


async def run_pipeline(
    ticket: str,
    target: str,
    event_bus: EventBus | None = None,
    stop_event: asyncio.Event | None = None,
    prior_summary: str | None = None,
) -> str:
    """Run the full TDD pipeline and return the final report text."""

    completed_stages: list[str] = []
    current_stage: str = "INIT"
    pipeline_session_id: str | None = None

    def _check_stop() -> None:
        """Raise PipelineStopped if the stop event is set."""
        if stop_event and stop_event.is_set():
            raise PipelineStopped(completed_stages, current_stage, tracker, pipeline_session_id)

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

    async def protect_test_files(input_data, tool_use_id, context):
        if current_stage not in ("GREEN", "REVIEW_GREEN", "SECURITY_GREEN", "QA_GREEN"):
            return {}
        file_path = input_data.get("tool_input", {}).get("file_path", "")
        if file_path and _is_test_file(file_path):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"[PIPELINE GUARDRAIL] Cannot modify test file "
                        f"{file_path} during {current_stage} stage. "
                        "Only implementation files should be changed."
                    ),
                }
            }
        return {}

    async def bash_guardrail(input_data, tool_use_id, context):
        command = input_data.get("tool_input", {}).get("command", "")
        for pattern in _BLOCKED_BASH_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"[PIPELINE GUARDRAIL] Blocked dangerous command: "
                            f"{command[:120]}"
                        ),
                    }
                }
        # Block cd to absolute paths outside the target directory
        norm_target = os.path.normpath(target)
        for cd_match in re.finditer(r"(?:^|[;&|])\s*cd\s+(/[^\s;|&]*)", command):
            cd_path = os.path.normpath(cd_match.group(1))
            if not cd_path.startswith(norm_target):
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"[PIPELINE GUARDRAIL] cd to {cd_path} is outside the "
                            f"target project directory {target}. Stay within {target}."
                        ),
                    }
                }
        return {}

    async def path_boundary_guardrail(input_data, tool_use_id, context):
        file_path = input_data.get("tool_input", {}).get("file_path", "")
        if file_path and os.path.isabs(file_path):
            norm_target = os.path.normpath(target)
            norm_file = os.path.normpath(file_path)
            if not (norm_file == norm_target or norm_file.startswith(norm_target + os.sep)):
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"[PIPELINE GUARDRAIL] Path {file_path} is outside the "
                            f"target project directory {target}. All operations must "
                            f"stay within {target}."
                        ),
                    }
                }
        return {}

    async def pre_compact_hook(input_data, tool_use_id, context):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreCompact",
                "customInstructions": (
                    "CRITICAL PIPELINE CONTEXT — preserve across compaction:\n"
                    f"  Current stage: {current_stage}\n"
                    f"  Test command: {test_cmd}\n"
                    f"  Test status: {tracker.summary()}\n"
                    f"  Completed stages: {', '.join(completed_stages)}\n"
                ),
            }
        }

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        model=PIPELINE_MODEL,
        cwd=target,
        max_turns=50,
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[protect_test_files, path_boundary_guardrail]),
                HookMatcher(matcher="Bash", hooks=[bash_guardrail]),
            ],
            "PreCompact": [
                HookMatcher(hooks=[pre_compact_hook]),
            ],
            "PostToolUse": [
                HookMatcher(matcher="Bash", hooks=[test_monitor_hook]),
            ],
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        # ── Stage 1 — PLAN ──
        current_stage = "PLAN"
        _check_stop()
        if prior_summary:
            plan_result = await run_stage(
                client,
                "STAGE 1 - PLAN (resume)",
                "Resuming from previous run — reviewing prior progress",
                _load_prompt("plan_resume", target=target, ticket=ticket, prior_summary=prior_summary),
                event_bus=event_bus,
            )
        else:
            plan_result = await run_stage(
                client,
                "STAGE 1 - PLAN",
                "Analyzing ticket and planning approach",
                _load_prompt("plan", target=target, ticket=ticket),
                event_bus=event_bus,
            )
        pipeline_session_id = plan_result.session_id
        completed_stages.append("PLAN")

        # ── Stage 2 — RED (Write Tests) ──
        current_stage = "RED"
        _check_stop()
        await run_stage(
            client,
            "STAGE 2 - RED",
            "Writing tests (TDD - expecting failures)",
            _load_prompt("red", target=target, test_cmd=test_cmd),
            event_bus=event_bus,
        )
        completed_stages.append("RED")

        # ── Stage 3 — GREEN (Implement) ──
        current_stage = "GREEN"
        _check_stop()
        await run_stage(
            client,
            "STAGE 3 - GREEN",
            "Implementing feature/fix to make tests pass",
            _load_prompt("green", target=target, test_cmd=test_cmd),
            event_bus=event_bus,
        )

        # ── Verification gate after GREEN ──
        gate = await _verify_and_emit(tracker, target, "STAGE 3", event_bus)
        completed_stages.append("GREEN")

        if gate.outcome != TestOutcome.PASS:
            for fix_attempt in range(1, MAX_GREEN_FIX_ATTEMPTS + 1):
                _check_stop()
                await run_stage(
                    client,
                    f"STAGE 3 - GREEN (fix attempt {fix_attempt}/{MAX_GREEN_FIX_ATTEMPTS})",
                    "Fixing failing tests based on actual test output",
                    _load_prompt(
                        "green_fix",
                        target=target,
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

        # ── Stage 4 — CODE REVIEW loop ──
        for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
            current_stage = "REVIEW"
            _check_stop()
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

            review_result = await run_stage(
                client,
                f"STAGE 4 - CODE REVIEW (round {iteration}/{MAX_REVIEW_ITERATIONS})",
                "Reviewing implementation for correctness and quality",
                _load_prompt("review", target=target, test_status_block=test_status_block),
                event_bus=event_bus,
            )
            review = review_result.text

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
            _check_stop()

            # RED — write tests for the issues found
            current_stage = "REVIEW_RED"
            await run_stage(
                client,
                f"STAGE 4.{iteration} - CODE REVIEW RED",
                "Writing tests for reviewer findings",
                _load_prompt("review_red", target=target, test_cmd=test_cmd),
                event_bus=event_bus,
            )

            # GREEN — fix the issues
            current_stage = "REVIEW_GREEN"
            _check_stop()
            await run_stage(
                client,
                f"STAGE 4.{iteration} - CODE REVIEW GREEN",
                "Fixing reviewer findings",
                _load_prompt("review_green", target=target, test_cmd=test_cmd),
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

        completed_stages.append("REVIEW")

        # ── Stage 5 — SECURITY REVIEW loop ──
        security_options = ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            permission_mode="bypassPermissions",
            model=SECURITY_MODEL,
            cwd=target,
            max_turns=30,
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_guardrail]),
                ],
            },
        )

        for sec_iteration in range(1, MAX_SECURITY_ITERATIONS + 1):
            current_stage = "SECURITY_REVIEW"
            _check_stop()

            async with ClaudeSDKClient(options=security_options) as security_client:
                security_result = await run_stage(
                    security_client,
                    f"STAGE 5 - SECURITY REVIEW (round {sec_iteration}/{MAX_SECURITY_ITERATIONS})",
                    "Scanning for leaked credentials, vulnerable packages, and insecure code",
                    _load_prompt("security_review", target=target),
                    event_bus=event_bus,
                )
            security_text = security_result.text

            if "SECURITY: APPROVED" in security_text:
                await _log(f"Security review APPROVED on round {sec_iteration}", event_bus)
                break

            if "SECURITY: ISSUES_FOUND" not in security_text:
                await _log(
                    "Security reviewer did not provide a clear verdict — treating as APPROVED",
                    event_bus,
                )
                break

            await _log(
                f"Security reviewer found issues on round {sec_iteration}, fixing...",
                event_bus,
            )

            if sec_iteration == MAX_SECURITY_ITERATIONS:
                await _log(
                    f"WARNING: Security issues persist after {MAX_SECURITY_ITERATIONS} rounds — proceeding to report.",
                    event_bus,
                )
                break

            # Fix security issues using the main client
            current_stage = "SECURITY_GREEN"
            _check_stop()
            await run_stage(
                client,
                f"STAGE 5.{sec_iteration} - SECURITY FIX",
                "Fixing security issues found by the security reviewer",
                _load_prompt("security_fix", target=target, security_issues=security_text, test_cmd=test_cmd),
                event_bus=event_bus,
            )

            # Verify tests still pass after security fix
            sec_gate = await _verify_and_emit(
                tracker, target, f"STAGE 5.{sec_iteration} security fix", event_bus
            )
            if sec_gate.outcome != TestOutcome.PASS:
                await _log(
                    f"Tests failing after security fix round {sec_iteration}: "
                    f"{sec_gate.failures} failures, {sec_gate.errors} errors",
                    event_bus,
                )

        completed_stages.append("SECURITY_REVIEW")

        # ── Stage 6 — QA loop ──
        qa_options = ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            permission_mode="bypassPermissions",
            model=QA_MODEL,
            cwd=target,
            max_turns=40,
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_guardrail]),
                ],
            },
        )

        for qa_iteration in range(1, MAX_QA_ITERATIONS + 1):
            current_stage = "QA"
            _check_stop()

            async with ClaudeSDKClient(options=qa_options) as qa_client:
                qa_result = await run_stage(
                    qa_client,
                    f"STAGE 6 - QA (round {qa_iteration}/{MAX_QA_ITERATIONS})",
                    "Testing the feature end-to-end against the running application",
                    _load_prompt("qa_review", target=target, ticket=ticket, test_cmd=test_cmd),
                    event_bus=event_bus,
                )
            qa_text = qa_result.text

            if "QA: APPROVED" in qa_text:
                await _log(f"QA APPROVED on round {qa_iteration}", event_bus)
                break

            if "QA: ISSUES_FOUND" not in qa_text:
                await _log(
                    "QA agent did not provide a clear verdict — treating as APPROVED",
                    event_bus,
                )
                break

            await _log(
                f"QA found issues on round {qa_iteration}, fixing...",
                event_bus,
            )

            if qa_iteration == MAX_QA_ITERATIONS:
                await _log(
                    f"WARNING: QA issues persist after {MAX_QA_ITERATIONS} rounds — proceeding to report.",
                    event_bus,
                )
                break

            # Fix QA issues using the main client
            current_stage = "QA_GREEN"
            _check_stop()
            await run_stage(
                client,
                f"STAGE 6.{qa_iteration} - QA FIX",
                "Fixing behavioral issues found by the QA agent",
                _load_prompt("qa_fix", target=target, qa_issues=qa_text, test_cmd=test_cmd),
                event_bus=event_bus,
            )

            # Verify unit tests still pass after QA fix
            qa_gate = await _verify_and_emit(
                tracker, target, f"STAGE 6.{qa_iteration} QA fix", event_bus
            )
            if qa_gate.outcome != TestOutcome.PASS:
                await _log(
                    f"Tests failing after QA fix round {qa_iteration}: "
                    f"{qa_gate.failures} failures, {qa_gate.errors} errors",
                    event_bus,
                )

        completed_stages.append("QA")

    # ── Final verification before report ──
    current_stage = "REPORT"
    _check_stop()
    final_verify = await _verify_and_emit(tracker, target, "FINAL", event_bus)

    # ── Stage 7 — REPORT (separate session, cheaper model) ──
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

    report_options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        model=REPORT_MODEL,
        cwd=target,
        max_turns=10,
    )
    async with ClaudeSDKClient(options=report_options) as report_client:
        report_result = await run_stage(
            report_client,
            "STAGE 7 - REPORT",
            "Generating final TDD report",
            _load_prompt("report", target=target, final_test_block=final_test_block),
            event_bus=event_bus,
        )

    completed_stages.append("REPORT")

    return report_result.text
