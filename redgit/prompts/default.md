# Default Commit Grouping Prompt

You are a senior software engineer. Analyze the following file changes and group them into logical commits.

## Guidelines

1. **Group by feature/purpose**: Files that work together should be in the same group
2. **Separate concerns**: Don't mix unrelated changes (e.g., config changes vs feature code)
3. **Atomic commits**: Each group should represent a single logical change
4. **Clear naming**: Use conventional commit format (feat/fix/refactor/chore)

## File Changes

{{FILES}}

## Instructions

- **IMPORTANT: Every single file listed above MUST be included in exactly one group**
- Do NOT skip any files - all files must be assigned to a group
- Create logical groups from the files above
- Each group should have a clear, single purpose
- Use English for commit messages
- Branch names should be kebab-case
- If a file doesn't fit any feature group, create a "chore" group for it