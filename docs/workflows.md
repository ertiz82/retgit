# Workflow Strategies

RedGit supports two workflow strategies for handling commits and branches.

## Overview

| Strategy | Best For | Branches | Push Behavior |
|----------|----------|----------|---------------|
| `local-merge` | Solo developers, small teams | Merged immediately | Push current branch |
| `merge-request` | Teams with code review | Kept for PR | Push each branch + create PR |

## Configuration

Set your strategy in `.redgit/config.yaml`:

```yaml
workflow:
  strategy: local-merge    # or: merge-request
  auto_transition: true
  create_missing_issues: ask
  default_issue_type: task
```

## Local Merge Strategy (Default)

The `local-merge` strategy immediately merges feature branches into your current branch after committing.

### How It Works

```
rg propose
```

1. AI analyzes changes and groups them
2. For each group:
   - Creates a feature branch from current branch
   - Commits the grouped files
   - Merges back into current branch
   - Deletes the feature branch
3. All commits are now on your current branch

```
rg push
```

4. Pushes current branch to remote
5. Optionally completes issues in task management

### Flow Diagram

```
Before:
  main ─────○ (HEAD)

After rg propose:
  main ─────○───●───●───● (HEAD, all commits merged)
               │   │   │
               └───┴───┴── feature branches (deleted)

After rg push:
  main ─────○───●───●───● (pushed to origin)
```

### When to Use

- Solo development
- Small teams without formal code review
- Fast iteration cycles
- Local feature development

### Example

```bash
# Make changes to multiple files
vim src/auth.py
vim src/models/user.py
vim tests/test_auth.py

# Propose commits
rg propose
# Output:
#   ✓ Committed and merged feature/PROJ-123-auth-system
#   ✓ Committed and merged feature/PROJ-124-user-model

# Push everything
rg push
# Output:
#   📤 Pushing current branch: main
#   ✓ Pushed to origin/main
```

## Merge Request Strategy

The `merge-request` strategy keeps feature branches separate for pull/merge request workflows.

### How It Works

```
rg propose
```

1. AI analyzes changes and groups them
2. For each group:
   - Creates a feature branch from current branch
   - Commits the grouped files
   - Returns to current branch (branch is kept)
3. Feature branches remain for later push

```
rg push --pr
```

4. Pushes each feature branch to remote
5. Creates pull/merge requests (if code_hosting configured)
6. Optionally completes issues

### Flow Diagram

```
Before:
  main ─────○ (HEAD)

After rg propose:
  main ─────○ (HEAD)
             ├── feature/PROJ-123-auth ────●
             └── feature/PROJ-124-user ────●

After rg push --pr:
  main ─────○ (HEAD)
             ├── feature/PROJ-123-auth ────● (pushed, PR created)
             └── feature/PROJ-124-user ────● (pushed, PR created)
```

### When to Use

- Team development with code review
- Projects requiring PR approval
- CI/CD pipelines triggered by PRs
- Open source contributions

### Example

```bash
# Configure merge-request strategy
# In .redgit/config.yaml:
# workflow:
#   strategy: merge-request

# Make changes
vim src/auth.py
vim src/models/user.py

# Propose commits
rg propose
# Output:
#   ✓ Committed to feature/PROJ-123-auth-system
#   ✓ Committed to feature/PROJ-124-user-model
#
#   Branches ready for push and PR creation.
#   Run 'rg push --pr' to push branches and create pull requests

# Push and create PRs
rg push --pr
# Output:
#   📦 Session: 2 branches, 2 issues
#
#   Pushing branches...
#   • feature/PROJ-123-auth-system
#     ✓ Pushed to origin/feature/PROJ-123-auth-system
#     ✓ PR created: https://github.com/user/repo/pull/42
#
#   • feature/PROJ-124-user-model
#     ✓ Pushed to origin/feature/PROJ-124-user-model
#     ✓ PR created: https://github.com/user/repo/pull/43
```

## Comparison

| Feature | local-merge | merge-request |
|---------|-------------|---------------|
| Branch lifetime | Temporary (deleted after merge) | Persistent (until PR merged) |
| Code review | After push (optional) | Before merge (via PR) |
| CI/CD trigger | On push to main | On PR creation |
| Conflict resolution | During propose | During PR merge |
| History | Linear (merge commits) | Branch-based |

## Switching Strategies

You can switch strategies at any time:

```yaml
# .redgit/config.yaml
workflow:
  strategy: merge-request  # Change from local-merge
```

**Note:** Switching strategies won't affect existing sessions. Complete or clear your current session before switching.

```bash
# Clear existing session
rg push  # or manually clear
```

## Code Hosting Integration

The `merge-request` strategy works best with code hosting integration:

```yaml
# .redgit/config.yaml
active:
  code_hosting: github

integrations:
  github:
    enabled: true
    owner: your-username
    repo: your-repo
    token: ${GITHUB_TOKEN}
```

With this configured, `rg push --pr` will automatically create pull requests.

## See Also

- [Configuration](configuration.md)
- [Commands Reference](commands.md)
- [GitHub Integration](integrations/github.md)
- [Jira Integration](integrations/jira.md)