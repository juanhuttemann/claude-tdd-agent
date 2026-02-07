from claude_agent_sdk import AgentDefinition

planner = AgentDefinition(
    description="Analyzes a ticket and the Rails codebase to produce a concrete implementation plan",
    prompt=(
        "You are a senior Rails architect. "
        "Given a ticket description and access to the codebase, produce a detailed plan:\n"
        "1. Identify which models, controllers, views, routes, or libs are involved.\n"
        "2. Describe the tests that should be written (file paths, test names, assertions).\n"
        "3. Describe the implementation changes needed (file paths, methods, logic).\n"
        "4. Note any migrations, config changes, or edge cases.\n"
        "Be specific — include file paths relative to the project root."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
)
