CRITICAL: The pipeline ran an independent test verification and found FAILING TESTS. This is the actual test output from a real subprocess — not your previous summary.

Command: {gate_command}
Exit code: {gate_exit_code}
Failures: {gate_failures}, Errors: {gate_errors}
Test output:
```
{gate_stdout}
```
Stderr:
```
{gate_stderr}
```

You MUST fix the implementation to make ALL tests pass. Do NOT modify test files. Do NOT claim failures are intentional. Run `{test_cmd}` after each fix to check progress.
