A TDD pipeline run was interrupted by the user. Your job is to assess the current state of the codebase and produce a clear, actionable summary that another agent can use to continue the work.

## Original Ticket

{ticket}

## Pipeline Progress

- **Completed stages:** {completed_stages}
- **Interrupted during:** {interrupted_stage}
- **Test status:** {test_status}

## Files Modified

{files_modified}

## Instructions

1. Read the modified files and any test files in the codebase to understand what has been done so far.
2. If tests exist, review them to understand what's passing and what's failing.
3. Produce a summary covering:
   - What was planned
   - What was implemented (be specific about files and changes)
   - What tests were written and their current status
   - What remains to be done to complete the ticket
   - Any issues or blockers observed

Write your summary as a clear, structured narrative that another developer or AI agent can use to pick up exactly where this run left off. Focus on being specific and actionable — reference exact file paths and describe the state of each component.
