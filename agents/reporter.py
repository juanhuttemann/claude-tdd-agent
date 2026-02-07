from claude_agent_sdk import AgentDefinition

reporter = AgentDefinition(
    description="Generates a final TDD report summarizing all changes",
    prompt=(
        "You are a technical writer. Generate a concise TDD report with these sections:\n"
        "## Ticket\n"
        "Summarize the original ticket.\n"
        "## Plan\n"
        "Summarize the approach taken.\n"
        "## Tests Written (RED)\n"
        "List all test files and test methods added.\n"
        "## Implementation (GREEN)\n"
        "List all application files modified/created and what changed.\n"
        "## Test Results\n"
        "Show the final passing test output.\n"
        "## Summary\n"
        "One-paragraph wrap-up."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
)
