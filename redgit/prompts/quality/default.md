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

## SOLID Principles Check

Flag violations as MEDIUM severity with type "solid":

- **S - Single Responsibility**: Class/function doing too many unrelated things (>3 distinct responsibilities)
- **O - Open/Closed**: Code requires modification instead of extension (hardcoded conditions that should be polymorphic)
- **L - Liskov Substitution**: Subclass breaks parent contract (overrides method with incompatible behavior)
- **I - Interface Segregation**: Class forced to implement unused methods (fat interface)
- **D - Dependency Inversion**: High-level module directly depends on low-level module (no abstraction)

Only flag CLEAR violations, not minor design preferences.

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
- 50-69: Has MEDIUM issues (including SOLID violations)
- 0-49: Has CRITICAL/HIGH issues

Threshold: {{THRESHOLD}}

## Response Format

Return ONLY this JSON, no markdown, no explanation:

{"score":85,"decision":"approve","summary":"No critical issues","issues":[]}

If issues found:

{"score":45,"decision":"reject","summary":"Found SQL injection","issues":[{"severity":"critical","type":"security","file":"api.py","line":42,"description":"User input directly in SQL query","suggestion":"Use parameterized query"}]}

For SOLID violations:

{"score":65,"decision":"reject","summary":"SOLID violation found","issues":[{"severity":"medium","type":"solid","file":"user_service.py","line":15,"description":"[SRP] UserService handles authentication, validation, and email sending","suggestion":"Split into AuthService, ValidationService, and EmailService"}]}

## Diff

{{DIFF}}
