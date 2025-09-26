# Fix specific lint issue (parameter: issue code or description)

## Variables

ISSUE_ID: $ARGUMENTS

## Instructions

1. Run "task lint-app" to identify all lint issues
2. Filter for issues matching "ISSUE_ID" (can be a specific error code like S607 or a description like "subprocess")
3. Analyze each matching issue and implement fixes according to best practices
4. For each fixed issue:
   - Explain the problem and why it's a concern
   - Show the original code
   - Explain your fix and its benefits
5. After implementing fixes, run "task lint-app" again to verify the issues are resolved
6. Summarize your changes and list any remaining issues grouped by type

Notes:
- Focus only on issues matching the specified ISSUE_ID
- Apply consistent fixes across similar issues
- For Python security issues (S-prefixed codes), consult Python security best practices
- For other issues, follow the appropriate linting tool's recommendations
