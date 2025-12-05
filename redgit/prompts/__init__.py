# Response schema that is appended to every prompt
RESPONSE_SCHEMA = '''
---
## CRITICAL REQUIREMENTS

**YOU MUST INCLUDE EVERY SINGLE FILE FROM THE LIST ABOVE.**
- Count the files in your response - it MUST equal the total number shown above
- If you skip ANY file, your response is INVALID
- Every file must appear in EXACTLY ONE group
- When in doubt, create a "chore" group for miscellaneous files

## Response Format

Respond ONLY with valid YAML in this exact format (no other text):
```yaml
groups:
  - purpose: "Brief description of what this group does"
    type: "feat"
    branch: "feat/short-description"
    commit_title: "feat(scope): short summary under 72 chars"
    commit_body: |
      - Detail about the change
      - Another detail
    files:
      - "path/to/file1.php"
      - "path/to/file2.php"
  - purpose: "Another group description"
    type: "fix"
    branch: "fix/another-description"
    commit_title: "fix(scope): short summary"
    commit_body: |
      - What was fixed
    files:
      - "path/to/file3.php"
```

## Rules
- type must be one of: feat, fix, refactor, chore, docs, test, style
- branch should be: {type}/{short-kebab-description}
- commit_title must be under 72 characters
- **MANDATORY: Include ALL files - do not skip any file**
- If a file doesn't fit a feature group, put it in a "chore" group
'''