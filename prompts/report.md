Generate a final TDD report for the following pipeline run.

## Ticket
{ticket}

## Implementation Plan
{plan}

## Final Test Results
{final_test_block}

The test results above are the FINAL AUTHORITATIVE results from an independent pipeline verification. Base your report on these — not on any earlier test runs.

## Code Review
{review_summary}

## QA Testing
{qa_summary}

## Security Review
{security_summary}

---

Use the implementation plan above to identify which files were created or modified. Read those specific files to enumerate the tests written (section 3) and implementation details (section 4). Do not read pre-existing files not mentioned in the plan.

Write a complete report with these sections:

1. **Ticket** — what was requested
2. **Plan** — how it was approached
3. **Tests Written** — what tests were added and what they verify
4. **Implementation** — what files were changed and how
5. **Code Review** — issues found and whether they were resolved
6. **QA Findings** — behavioral testing results
7. **Security Review** — security findings and whether they were resolved
8. **Test Results** — final pass/fail status with counts
9. **Summary** — one paragraph conclusion

If any tests are still failing, clearly state that — do NOT claim failures are intentional or expected.
