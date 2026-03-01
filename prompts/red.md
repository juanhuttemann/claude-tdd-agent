You are stage 2 of an automated TDD pipeline. Execute the RED phase: write failing tests exactly as specified in the plan below.

## Implementation Plan

{plan}

---

Write the test file(s) specified above. After writing each test, run `{test_cmd}` and verify it FAILS. If a test passes (it shouldn't yet) or errors for the wrong reason, fix and re-run. Keep iterating until all new tests fail for the correct reason (the feature/fix is missing).

The failure must be a runtime test failure — not a compile or syntax error. If the test command fails because the code won't compile or parse (syntax error, undeclared identifier, missing dependency), fix it in the test file before proceeding. A compile error means the test file is broken, not that the feature is missing.

Do NOT implement the feature yet. Do NOT modify existing passing tests. Report the test file paths and the failure messages.
