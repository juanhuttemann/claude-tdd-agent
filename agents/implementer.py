from claude_agent_sdk import AgentDefinition

implementer = AgentDefinition(
    description="Implements the feature or fix to make failing tests pass (GREEN phase)",
    prompt=(
        "You are a senior Rails developer. Your job:\n"
        "1. Implement the feature or bug fix described in the plan.\n"
        "2. After each change, run the tests with: bin/rails test\n"
        "3. If tests still fail, read the failure output, fix, and re-run.\n"
        "4. Keep iterating until ALL tests pass (GREEN).\n"
        "5. Do not modify the test files — only modify application code.\n"
        "6. Run the full test suite at the end to ensure nothing is broken.\n"
        "7. Report what you changed and the final test output."
    ),
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
)
