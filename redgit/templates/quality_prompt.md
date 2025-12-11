# Code Quality Analysis

Analyze git diff for real issues only. Ignore style preferences.

## ONLY Flag These Issues

CRITICAL/HIGH (must fix):
- Hardcoded passwords, API keys, secrets
- SQL injection, XSS, command injection
- Null/undefined access without check
- Infinite loops, deadlocks
- Syntax errors that break code execution

MEDIUM (should fix):
- Resource not closed (files, connections)
- Race conditions
- Unhandled exceptions that crash app
- Stray characters or typos that affect logic (e.g., lone semicolons, random symbols)

LOW (optional):
- N+1 queries
- Duplicate code blocks (>10 lines)
- Dead code (unreachable statements)

## DO NOT Flag

- Missing comments or docstrings
- Variable naming preferences
- Import ordering
- Line length
- Formatting issues
- Type hints missing
- Functions that work correctly but "could be simpler"

## Scoring

- 90-100: No issues found
- 70-89: Only LOW issues
- 50-69: Has MEDIUM issues
- 0-49: Has CRITICAL/HIGH issues

Threshold: {{THRESHOLD}}

## Response Format

Return ONLY this JSON, no markdown, no explanation:

{"score":85,"decision":"approve","summary":"No critical issues","issues":[]}

If issues found:

{"score":45,"decision":"reject","summary":"Found SQL injection","
issues":[{"severity":"critical","type":"security","file":"api.py","line":42,"description":"User input directly in SQL query","suggestion":"Use parameterized query"}]}

## Diff

{{DIFF}}
