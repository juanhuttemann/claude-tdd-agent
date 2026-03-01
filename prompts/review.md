Review ALL the changes made in this pipeline run.

{test_status_block}

The test results above are AUTHORITATIVE — they come from an independent test run by the pipeline, not from any previous agent output. If exit code is NOT 0, tests are FAILING and you MUST issue VERDICT: CHANGES_NEEDED regardless of any other consideration.

Read every file that was created or modified — both tests and implementation — then evaluate each category below:

**Correctness**
- Does the implementation fully satisfy the ticket requirements?
- Are return values, status codes, and side effects exactly right?
- Are all error cases handled (invalid input, not found, unauthorized)?

**Edge cases**
- Empty input, zero, nil/null/None, empty collections?
- Boundary conditions (off-by-one, max/min values)?
- Repeated or concurrent calls?

**Test quality**
- Do tests cover the requirements or just the happy path?
- Are assertions specific (exact values) rather than "truthy" checks?
- Is any meaningful behaviour left untested?

**Code quality**
- No duplicated logic that should be extracted into a helper
- Variable and function names clear and consistent with the codebase style
- No dead code, commented-out blocks, or debugging statements

**Robustness**
- No unhandled exceptions that could crash the application
- External calls (DB, HTTP, file I/O) have appropriate error handling
- No obvious performance traps (N+1 queries, unbounded loops over large data)

End your review with exactly one of:
  VERDICT: APPROVED
  VERDICT: CHANGES_NEEDED
If CHANGES_NEEDED, list each specific issue that must be fixed.
