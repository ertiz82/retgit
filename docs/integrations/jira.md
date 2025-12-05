# Jira Integration

Full-featured Jira Cloud integration with Scrum and Kanban support.

## Installation

```bash
rg integration install jira
```

## Configuration

```yaml
# .redgit/config.yaml
active:
  task_management: jira

integrations:
  jira:
    site: https://your-company.atlassian.net
    email: developer@company.com
    project_key: PROJ
    board_type: scrum          # scrum | kanban | none
    board_id: null             # Auto-detected if empty
    story_points_field: customfield_10016
    branch_pattern: "feature/{issue_key}-{description}"
```

## Environment Variables

```bash
# Required
export JIRA_API_TOKEN="your-api-token"
```

## API Token Setup

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a descriptive label (e.g., "RedGit")
4. Copy the token
5. Store as `JIRA_API_TOKEN` environment variable

## Features

### Issue Fetching

RedGit fetches issues where:
- Assigned to current user
- Status is "To Do", "In Progress", "Open", or "In Development"
- In current sprint (for Scrum boards)

### Status Transitions

```
To Do ──► In Progress ──► Done
         (on commit)      (on push)
```

When you run `rg propose`:
- Issues are automatically transitioned to "In Progress"

When you run `rg push`:
- Issues can be transitioned to "Done" (with confirmation)

### Branch Naming

Default pattern: `feature/{issue_key}-{description}`

Example: `feature/PROJ-123-add-user-authentication`

Custom patterns can use these variables:
- `{issue_key}` - The issue key (e.g., PROJ-123)
- `{description}` - Kebab-case description from issue summary
- `{issue_type}` - Issue type (bug, story, task, etc.)

### Sprint Support

For Scrum boards:
- Auto-detects active sprint
- New issues are added to active sprint
- Shows sprint info in `rg propose`

## Usage Examples

### Propose with Jira Issues

```bash
rg propose
```

Output:
```
📋 Active issues from Jira:
  1. PROJ-123 [In Progress] Add user authentication
  2. PROJ-124 [To Do] Fix login bug
  3. PROJ-125 [To Do] Update documentation

Select issues to work on (comma-separated, or 'all'):
```

### Push and Complete Issues

```bash
rg push

# Output:
# 📤 Pushing current branch: feature/PROJ-123-add-user-authentication
# ✓ Pushed to origin/feature/PROJ-123-add-user-authentication
# Mark PROJ-123 as Done? [Y/n]
# ✓ PROJ-123 → Done
```

### Create New Issue

```bash
rg propose --new-issue
```

Interactive wizard:
```
Issue type: [Story/Bug/Task]
Summary: Add password reset feature
Description: Users should be able to reset their password via email
Story points: 3

✓ Created PROJ-126: Add password reset feature
```

## Jira API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /rest/api/3/search` | Search issues (JQL) |
| `GET /rest/api/3/issue/{key}` | Get issue details |
| `POST /rest/api/3/issue` | Create new issue |
| `POST /rest/api/3/issue/{key}/comment` | Add comment |
| `GET /rest/api/3/issue/{key}/transitions` | Get available transitions |
| `POST /rest/api/3/issue/{key}/transitions` | Transition issue |
| `GET /rest/agile/1.0/board` | List boards |
| `GET /rest/agile/1.0/board/{id}/sprint` | Get sprints |
| `POST /rest/agile/1.0/sprint/{id}/issue` | Add issue to sprint |

## Troubleshooting

### "Authentication failed"

1. Check if `JIRA_API_TOKEN` is set:
   ```bash
   echo $JIRA_API_TOKEN
   ```

2. Verify the token is valid at [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

3. Check email in config matches the token owner

### "No issues found"

1. Verify you have issues assigned to you
2. Check the project key is correct
3. Ensure issues are in the current sprint (for Scrum)

### "Board not found"

1. Remove `board_id` from config to auto-detect
2. Or manually find your board ID in Jira URL:
   ```
   https://your-company.atlassian.net/jira/software/projects/PROJ/boards/123
                                                                        ^^^
   ```

## See Also

- [Integrations Overview](../integrations.md)
- [GitHub Integration](github.md)