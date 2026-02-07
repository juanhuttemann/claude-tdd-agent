from dotenv import load_dotenv
import asyncio
import os
import sys

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from agents import AGENTS
from pipeline import print_banner, run_stage

load_dotenv()

TICKET_PATH = os.path.join(os.path.dirname(__file__), "ticket.md")
TARGET_APP = "/home/xh/testapp"
MAX_REVIEW_ITERATIONS = 3


async def main() -> None:
    # 1. Read the ticket
    if not os.path.exists(TICKET_PATH):
        print(f"Error: {TICKET_PATH} not found. Create a ticket.md with your bug or feature description.")
        sys.exit(1)

    with open(TICKET_PATH) as f:
        ticket = f.read().strip()

    print_banner("INIT", "TDD Agent Pipeline")
    print(f"  Ticket: {TICKET_PATH}")
    print(f"  Target: {TARGET_APP}")
    print(f"  Ticket content:\n  {ticket[:200]}{'...' if len(ticket) > 200 else ''}\n")

    # 2. Configure options
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        agents=AGENTS,
        cwd=TARGET_APP,
        max_turns=50,
    )

    # 3. Orchestrate the TDD pipeline
    async with ClaudeSDKClient(options=options) as client:
        # Stage 1 — PLAN
        await run_stage(
            client,
            "STAGE 1 - PLAN",
            "Analyzing ticket and planning approach",
            (
                f"Here is the ticket to implement:\n\n---\n{ticket}\n---\n\n"
                "Analyze the Rails codebase in the current directory and produce a detailed "
                "implementation plan. Include specific file paths for tests and implementation. "
                "Use the Glob and Read tools to explore the codebase structure first."
            ),
        )

        # Stage 2 — RED (Write Tests)
        await run_stage(
            client,
            "STAGE 2 - RED",
            "Writing tests (TDD - expecting failures)",
            (
                "Now execute the RED phase of TDD.\n\n"
                "Based on the plan above, write the minitest test file(s). "
                "After writing each test, run it with `bin/rails test <path>` and verify it FAILS. "
                "If a test passes (it shouldn't yet) or errors for the wrong reason, fix and re-run. "
                "Keep iterating until all new tests fail for the correct reason (the feature/fix is missing). "
                "Report the test file paths and the failure messages."
            ),
        )

        # Stage 3 — GREEN (Implement)
        await run_stage(
            client,
            "STAGE 3 - GREEN",
            "Implementing feature/fix to make tests pass",
            (
                "Now execute the GREEN phase of TDD.\n\n"
                "Implement the feature or fix described in the plan. "
                "Do NOT modify the test files. "
                "After each change, run `bin/rails test` to check progress. "
                "Keep iterating until ALL tests pass. "
                "Then run the full test suite to ensure nothing is broken. "
                "Report what you changed and the final test output."
            ),
        )

        # Stage 4 — REVIEW (loops back to RED → GREEN if issues found)
        for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
            review = await run_stage(
                client,
                f"STAGE 4 - REVIEW (round {iteration}/{MAX_REVIEW_ITERATIONS})",
                "Reviewing implementation",
                (
                    "Review ALL the changes made so far.\n\n"
                    "Read every file that was created or modified — both tests and implementation. "
                    "Run `bin/rails test` to verify all tests pass. "
                    "Check for correctness, missing edge cases, Rails conventions, security, and code quality. "
                    "End your review with exactly one of:\n"
                    "  VERDICT: APPROVED\n"
                    "  VERDICT: CHANGES_NEEDED\n"
                    "If CHANGES_NEEDED, list the specific issues that must be fixed."
                ),
            )

            if "VERDICT: APPROVED" in review:
                print(f"  Review APPROVED on round {iteration}")
                break

            print(f"  Review found issues on round {iteration}, looping back...")

            # RED — write tests for the issues found
            await run_stage(
                client,
                f"STAGE 4.{iteration} - RED (fix)",
                "Writing tests for reviewer findings",
                (
                    "The reviewer found issues. Based on the review feedback above, "
                    "write new or updated minitest tests that cover the problems identified. "
                    "Run the tests with `bin/rails test` and confirm the new tests FAIL (RED). "
                    "Do not fix the implementation yet — only write/update tests."
                ),
            )

            # GREEN — fix the issues
            await run_stage(
                client,
                f"STAGE 4.{iteration} - GREEN (fix)",
                "Fixing reviewer findings",
                (
                    "Now fix the issues identified by the reviewer. "
                    "Do NOT modify the test files. "
                    "After each change, run `bin/rails test` to check progress. "
                    "Keep iterating until ALL tests pass (GREEN). "
                    "Report what you changed and the final test output."
                ),
            )
        else:
            print(f"  Review did not approve after {MAX_REVIEW_ITERATIONS} rounds — proceeding to report.")

        # Stage 5 — REPORT
        report = await run_stage(
            client,
            "STAGE 5 - REPORT",
            "Generating final TDD report",
            (
                "Generate a final TDD report. "
                "Review the test files that were written, the implementation changes made, "
                "and any review iterations that occurred. "
                "Run `bin/rails test` one last time to confirm everything passes. "
                "Include all sections: Ticket, Plan, Tests Written, Implementation, "
                "Review Iterations, Test Results, Summary."
            ),
        )

        # Print the report
        print("\n" + "=" * 60)
        print("  FINAL REPORT")
        print("=" * 60)
        print(report)

    print("\ndone")


if __name__ == "__main__":
    asyncio.run(main())
