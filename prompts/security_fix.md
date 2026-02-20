The security reviewer has identified the following security issues:

{security_issues}

Fix ALL of these security issues in the implementation files. Do NOT modify test files.

Run `git diff --name-only HEAD~1 HEAD 2>/dev/null || git status --short` first to confirm which files are in scope.

For each issue:
- **Leaked credentials**: Remove hardcoded secrets and replace with environment variable references (e.g., `ENV['SECRET_KEY']`, `process.env.SECRET_KEY`, `os.environ['SECRET_KEY']`).
- **Vulnerable packages**: Update the dependency to a patched version. If no fix is available, add a comment documenting the accepted risk.
- **Vulnerable code**: Refactor to safe alternatives — use parameterized queries instead of string interpolation for SQL, validate and sanitize user input, escape output before rendering, restrict file paths, etc.

After fixing, run the tests to confirm nothing is broken:
```
{test_cmd}
```

Be thorough — address every issue listed above.
