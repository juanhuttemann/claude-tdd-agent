The QA engineer found the following issues when testing the feature end-to-end:

{qa_issues}

Fix ALL of these issues in the implementation files. Do NOT modify test files.

Run `git diff --name-only HEAD~1 HEAD 2>/dev/null || git status --short` first to confirm which files are in scope.

These are runtime/behavioral failures — the code runs but produces wrong results or crashes under real usage. Focus on:
- Incorrect logic that produces wrong output
- Missing validations that cause crashes on bad input
- Wrong HTTP status codes or response shapes
- Database queries or side effects that don't work correctly

After fixing, run the unit tests to confirm nothing is broken:
```
{test_cmd}
```

Address every issue listed above.
