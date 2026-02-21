"""Summarization agent for stopped TDD pipelines.

When a user stops a running pipeline, this module spins up a short-lived
Claude agent session to read the codebase and produce a structured summary
of what was completed, what's in progress, and what's failing.
"""

import json
import os
import time

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from events import EventBus
from pipeline import run_stage
from test_tracker import TestTracker
from test_verifier import verify_tests

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
SUMMARIZE_MODEL = os.getenv("SUMMARIZE_MODEL", "sonnet") or None


def _load_prompt(name: str, **kwargs: str) -> str:
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        template = f.read()
    return template.format(**kwargs) if kwargs else template


async def summarize_pipeline(
    ticket: str,
    target: str,
    completed_stages: list[str],
    interrupted_stage: str,
    tracker: TestTracker,
    event_history: list[dict],
    event_bus: EventBus | None = None,
) -> dict:
    """Run a summarization agent and return a structured summary dict.

    The agent reads modified files and test files, assesses current state,
    and produces a JSON summary that can be used to resume in a new session.
    """
    if event_bus:
        await event_bus.emit({
            "type": "log",
            "data": {"message": "Running summarization agent..."},
        })

    # Run independent test verification to get current test status
    test_result = await verify_tests(tracker, target)
    test_status = {
        "passing": test_result.outcome.value == "pass",
        "total": test_result.total_tests,
        "failures": test_result.failures,
        "errors": test_result.errors,
        "command": test_result.command,
    }

    # Extract files modified from event history (tool events with Write/Edit)
    files_modified = set()
    for event in event_history:
        if event.get("type") == "tool":
            data = event.get("data", {})
            tool = data.get("tool", "")
            inp = data.get("input", {})
            if tool in ("Write", "Edit") and "file_path" in inp:
                fpath = inp["file_path"]
                # Make relative to target if possible
                if isinstance(fpath, str):
                    try:
                        fpath = os.path.relpath(fpath, target)
                    except ValueError:
                        pass
                    files_modified.add(fpath)

    # Build context for the summarization agent
    files_list = "\n".join(f"  - {f}" for f in sorted(files_modified)) or "  (none detected)"
    test_status_str = (
        f"Passing: {test_status['passing']}, "
        f"Total: {test_status['total']}, "
        f"Failures: {test_status['failures']}, "
        f"Errors: {test_status['errors']}"
    )

    prompt = _load_prompt(
        "summarize",
        ticket=ticket[:500],
        completed_stages=", ".join(completed_stages) or "(none)",
        interrupted_stage=interrupted_stage,
        test_status=test_status_str,
        files_modified=files_list,
    )

    # Fork the pipeline session if available so the summarizer has full context,
    # otherwise fall back to a fresh session.
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Bash"],
        permission_mode="bypassPermissions",
        model=SUMMARIZE_MODEL,
        cwd=target,
        max_turns=15,
    )

    summary_text = ""
    async with ClaudeSDKClient(options=options) as client:
        result = await run_stage(
            client,
            "SUMMARIZE",
            "Generating pipeline summary",
            prompt,
            event_bus=event_bus,
        )
        summary_text = result.text

    # Build the structured summary
    summary = {
        "ticket": ticket[:1000],
        "target": target,
        "completed_stages": completed_stages,
        "interrupted_stage": interrupted_stage,
        "test_status": test_status,
        "files_modified": sorted(files_modified),
        "summary": summary_text,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Save to target directory
    summary_path = os.path.join(target, ".tdd_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    if event_bus:
        await event_bus.emit({
            "type": "log",
            "data": {"message": f"Summary saved to {summary_path}"},
        })

    return summary
