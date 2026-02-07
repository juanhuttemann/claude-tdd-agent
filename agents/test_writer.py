from claude_agent_sdk import AgentDefinition

test_writer = AgentDefinition(
    description="Writes minitest tests following TDD (RED phase) and verifies they fail",
    prompt=(
        "You are a TDD expert for Rails with minitest. Your job:\n"
        "1. Write the test file(s) described in the plan.\n"
        "2. Follow Rails minitest conventions (test/models/, test/controllers/, etc.).\n"
        "3. After writing each test file, run the tests with: bin/rails test <test_file>\n"
        "4. The tests MUST FAIL (RED) because the feature/fix is not implemented yet.\n"
        "5. If a test passes unexpectedly, revisit and strengthen it.\n"
        "6. If a test errors for the wrong reason (syntax, missing require), fix and re-run.\n"
        "7. Keep iterating until all new tests fail for the RIGHT reason.\n"
        "8. Report which tests you wrote and their failure messages."
    ),
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
)
