# GitHub Integration

GitHub integration for repository operations and pull request creation.

## Installation

```bash
rg integration install github
```

## Configuration

```yaml
# .redgit/config.yaml
active:
  code_hosting: github

integrations:
  github:
    owner: your-username
    repo: your-repo
    default_base: main
    auto_pr: false
```

## Environment Variables

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

## Token Setup

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (Full control of private repositories)
4. Copy and store as `GITHUB_TOKEN`

### Fine-grained Tokens (Alternative)

For more security, use fine-grained tokens:
1. Go to [Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click "Generate new token"
3. Select repository access
4. Required permissions:
   - Contents: Read and write
   - Pull requests: Read and write

## Features

### Pull Request Creation

```bash
rg push --pr
```

Creates a PR with:
- **Title**: Issue key + branch description
- **Body**: References to linked issues
- **Base**: Configured default branch (main/master)

### Auto-detect Repository

If `owner` and `repo` are not set, RedGit auto-detects from git remote:

```bash
git remote -v
# origin  git@github.com:username/repo.git (fetch)
#         ^^^^^^^^ ^^^^
#         owner    repo
```

### Push with Tags

```bash
rg push
# Automatically pushes tags along with branch
```

## Usage Examples

### Push and Create PR

```bash
rg push --pr

# Output:
# 📤 Pushing current branch: feature/add-user-auth
# ✓ Pushed to origin/feature/add-user-auth
# ✓ PR created: https://github.com/owner/repo/pull/42
```

### Push Branch Only (No PR)

```bash
rg push
```

### Push Without Tags

```bash
rg push --no-tags
```

## Workflow Strategies

### Merge Request Strategy

Best for teams using PR-based workflows:

```yaml
# .redgit/config.yaml
workflow:
  strategy: merge-request
```

Behavior:
1. `rg propose` creates feature branches
2. `rg push` pushes branches to remote
3. `rg push --pr` creates pull requests
4. Merge via GitHub UI

### Local Merge Strategy

Best for solo developers or trunk-based development:

```yaml
# .redgit/config.yaml
workflow:
  strategy: local-merge
```

Behavior:
1. `rg propose` creates feature branches
2. `rg push` merges locally to base branch and pushes

## GitHub API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /repos/{owner}/{repo}/pulls` | Create pull request |
| `GET /repos/{owner}/{repo}` | Get repository info |
| `GET /repos/{owner}/{repo}/branches` | List branches |

## Troubleshooting

### "Authentication failed"

1. Check if `GITHUB_TOKEN` is set:
   ```bash
   echo $GITHUB_TOKEN
   ```

2. Verify token has required permissions
3. Token might be expired - generate a new one

### "Repository not found"

1. Check `owner` and `repo` in config
2. Verify you have access to the repository
3. For private repos, ensure token has `repo` scope

### "PR creation failed"

1. Ensure you've pushed the branch first
2. Check if a PR already exists for this branch
3. Verify base branch exists (main/master)

## SSH vs HTTPS

RedGit uses your existing git remote configuration:

**SSH** (recommended):
```bash
git remote set-url origin git@github.com:owner/repo.git
```

**HTTPS**:
```bash
git remote set-url origin https://github.com/owner/repo.git
```

For HTTPS, you may need to configure git credential helper for push operations.

## See Also

- [Integrations Overview](../integrations.md)
- [Jira Integration](jira.md)