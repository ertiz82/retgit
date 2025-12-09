# Jira Integration

Full-featured Jira Cloud integration with Scrum and Kanban support, hierarchical issue management, and advanced sprint operations.

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

    # Custom status mappings (optional)
    # Override default status names for your Jira workflow
    statuses:
      todo:
        - "To Do"
        - "Backlog"
        - "Open"
      in_progress:
        - "In Progress"
        - "In Development"
        - "Devam Ediyor"        # Turkish example
      done:
        - "Done"
        - "Resolved"
        - "Closed"
        - "Tamamlandı"          # Turkish example

    # Custom issue type IDs (optional)
    # Override if your Jira uses different type IDs
    issue_types:
      task: "10003"
      story: "10004"
      bug: "10007"
      epic: "10001"

    # Issue language (optional)
    # Set this to create Jira issues in a different language than commits
    # Commits will always be in English, but issue titles will be in this language
    issue_language: tr   # Turkish, or: en, de, fr, es, pt, it, ru, zh, ja, ko, ar
```

### Issue Language

When `issue_language` is set, RedGit will:
- Keep commit messages in **English** (following conventional commits)
- Generate Jira issue titles in the **specified language**

This is useful for teams that:
- Follow English commit conventions for code consistency
- Use a local language for Jira boards to improve readability for non-technical stakeholders

**Supported Languages:**
| Code | Language |
|------|----------|
| `tr` | Turkish |
| `en` | English |
| `de` | German |
| `fr` | French |
| `es` | Spanish |
| `pt` | Portuguese |
| `it` | Italian |
| `ru` | Russian |
| `zh` | Chinese |
| `ja` | Japanese |
| `ko` | Korean |
| `ar` | Arabic |

**Example:**
```yaml
integrations:
  jira:
    issue_language: tr
```

With this config:
- Commit: `feat: add user authentication`
- Jira Issue: `Kullanıcı kimlik doğrulama özelliği eklendi`

### Status Mapping

RedGit uses status mappings to transition issues between workflow states. The default mappings cover common Jira configurations:

| Status Key | Default Values |
|------------|---------------|
| `todo` | "To Do", "Open", "Backlog" |
| `in_progress` | "In Progress", "In Development", "In Review" |
| `done` | "Done", "Closed", "Resolved", "Complete" |

**Custom Workflows:** If your Jira board uses different status names (e.g., Turkish, custom workflow), add them to the `statuses` config. RedGit will try each status name in order until one succeeds.

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

## CLI Commands

### Basic Commands

| Command | Description |
|---------|-------------|
| `rg jira status` | Show current sprint issues |
| `rg jira issue <key>` | Show issue details |
| `rg jira search <jql>` | Search issues with JQL |
| `rg jira assign <key> <user>` | Assign issue to user |
| `rg jira transition <key> <status>` | Change issue status |
| `rg jira comment <key> <text>` | Add comment to issue |

### Issue Creation

```bash
# Create a simple task
rg jira create "Fix login bug" --type bug

# Create with full options
rg jira create "User authentication" \
  --type story \
  --description "Implement JWT-based auth" \
  --points 5 \
  --labels "backend,security" \
  --assignee "john.doe@company.com"

# Create under an Epic
rg jira create "Login API endpoint" \
  --type story \
  --epic PROJ-100

# Create and add to sprint
rg jira create "Quick fix" --type task --sprint 123
```

**Options:**
- `-t, --type` - Issue type (story, task, bug, epic)
- `-e, --epic` - Parent Epic key
- `-d, --description` - Issue description
- `-p, --points` - Story points
- `-l, --labels` - Comma-separated labels
- `-a, --assignee` - Assignee email or account ID
- `-s, --sprint` - Sprint ID to add issue to

### Issue Linking

```bash
# Show available link types
rg jira link-types

# Link two issues (default: Blocks)
rg jira link PROJ-123 PROJ-124

# Link with specific type
rg jira link PROJ-123 PROJ-124 --type "is blocked by"

# Show all links for an issue
rg jira links PROJ-123
```

**Common Link Types:**
- `Blocks` / `is blocked by`
- `Relates` / `relates to`
- `Clones` / `is cloned by`
- `Duplicate` / `is duplicated by`

### Epic Management

```bash
# Show all issues under an Epic
rg jira epic PROJ-100

# Output:
# Epic: PROJ-100 - User Management System
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Stories (3):
#   PROJ-101 [Done] User registration
#   PROJ-102 [In Progress] User login
#   PROJ-103 [To Do] Password reset
#
# Tasks (2):
#   PROJ-104 [Done] Setup database schema
#   PROJ-105 [To Do] Write unit tests
```

### Sprint Management

```bash
# List all sprints
rg jira sprints

# Show only future sprints
rg jira sprints --future

# Create a new sprint
rg jira create-sprint "Sprint 15" \
  --goal "Complete authentication module" \
  --start "2025-01-15" \
  --end "2025-01-29"

# Move issues to a sprint
rg jira move-sprint PROJ-123,PROJ-124,PROJ-125 456

# Move to next future sprint
rg jira move-sprint PROJ-123 --future
```

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

### Hierarchical Issue Management

RedGit supports Jira's issue hierarchy:

```
Epic (PROJ-100)
├── Story (PROJ-101)
│   ├── Task (PROJ-111)
│   └── Task (PROJ-112)
├── Story (PROJ-102)
└── Bug (PROJ-103)
```

**Creating Hierarchies:**
```bash
# Create an Epic
rg jira create "User Authentication System" --type epic

# Create Stories under Epic
rg jira create "Login Flow" --type story --epic PROJ-100
rg jira create "Registration Flow" --type story --epic PROJ-100

# Create Tasks under Story (next-gen projects)
rg jira create "Implement JWT" --type task --epic PROJ-101
```

### Bulk Operations

The integration supports efficient bulk operations:

```python
# Bulk create (used by Scout sync)
issues = [
    {"summary": "Task 1", "issue_type": "Task"},
    {"summary": "Task 2", "issue_type": "Task"},
]
created = jira.bulk_create_issues(issues)

# Bulk assign
assignments = {
    "PROJ-123": "user-account-id-1",
    "PROJ-124": "user-account-id-2",
}
jira.bulk_assign_issues(assignments)

# Bulk transition
transitions = {
    "PROJ-123": "In Progress",
    "PROJ-124": "Done",
}
jira.bulk_transition_issues(transitions)
```

## Usage Examples

### Propose with Jira Issues

```bash
rg propose
```

Output:
```
Active issues from Jira:
  1. PROJ-123 [In Progress] Add user authentication
  2. PROJ-124 [To Do] Fix login bug
  3. PROJ-125 [To Do] Update documentation

Select issues to work on (comma-separated, or 'all'):
```

### Direct Task Commit (--task flag)

When you know which task you're working on, use `--task` to skip AI analysis and commit all changes to a specific issue:

```bash
# Using just the issue number (project key added automatically)
rg propose --task 123

# Using full issue key
rg propose -t PROJ-123
```

This will:
1. Fetch the issue details from Jira (title, description, status)
2. Create a branch using `branch_pattern` (e.g., `feature/PROJ-123-add-user-auth`)
3. Commit all changes with the issue title as commit message
4. Add a comment to the Jira issue
5. Transition the issue to "In Progress" (if `auto_transition` is enabled)

**Example Output:**
```
📋 Task management: jira
✓ Found: PROJ-123 - Add user authentication
   Status: To Do

📁 5 files will be committed:
   • src/auth/login.py
   • src/auth/jwt.py
   • tests/test_auth.py
   ... and 2 more

📝 Commit:
   Title: PROJ-123: Add user authentication
   Branch: feature/PROJ-123-add-user-authentication
   Files: 5

Proceed? [Y/n]: y
✓ Committed and merged feature/PROJ-123-add-user-authentication
✓ Comment added to PROJ-123
→ PROJ-123 moved to In Progress

✅ All changes committed to PROJ-123
Run 'rg push' to push to remote
```

**When to use `--task`:**
- You're working on a single task
- You want to skip AI analysis for faster commits
- You want all changes in one commit linked to a specific issue

### Push and Complete Issues

```bash
rg push

# Output:
# Pushing current branch: feature/PROJ-123-add-user-authentication
# Pushed to origin/feature/PROJ-123-add-user-authentication
# Mark PROJ-123 as Done? [Y/n]
# PROJ-123 -> Done
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

Created PROJ-126: Add password reset feature
```

### Complete Workflow Example

```bash
# 1. Create an Epic for the feature
rg jira create "Payment System" --type epic
# Created: PROJ-200

# 2. Create Stories under the Epic
rg jira create "Credit Card Processing" --type story --epic PROJ-200 --points 8
rg jira create "Invoice Generation" --type story --epic PROJ-200 --points 5

# 3. Set up dependencies
rg jira link PROJ-202 PROJ-201 --type "is blocked by"

# 4. Add to sprint
rg jira move-sprint PROJ-201,PROJ-202 --future

# 5. View the Epic structure
rg jira epic PROJ-200
```

## API Methods

### Core Methods

| Method | Description |
|--------|-------------|
| `get_active_issues()` | Get issues assigned to current user |
| `get_issue(key)` | Get single issue details |
| `create_issue(...)` | Create a new issue |
| `transition_issue(key, status)` | Change issue status |
| `add_comment(key, text)` | Add comment to issue |
| `assign_issue(key, account_id)` | Assign issue to user |

### Hierarchy Methods

| Method | Description |
|--------|-------------|
| `create_issue_with_parent(...)` | Create issue under Epic/Story |
| `get_epic_issues(epic_key)` | Get all issues under an Epic |
| `set_epic_link(issue_key, epic_key)` | Link issue to Epic |
| `get_epic_link_field()` | Discover Epic Link custom field |

### Linking Methods

| Method | Description |
|--------|-------------|
| `link_issues(source, target, type)` | Create link between issues |
| `get_issue_links(key)` | Get all links for an issue |
| `get_link_types()` | Get available link types |

### Bulk Methods

| Method | Description |
|--------|-------------|
| `bulk_create_issues(issues)` | Create multiple issues |
| `bulk_assign_issues(assignments)` | Assign multiple issues |
| `bulk_transition_issues(transitions)` | Transition multiple issues |

### Sprint Methods

| Method | Description |
|--------|-------------|
| `get_sprints()` | Get all sprints |
| `get_active_sprint()` | Get current active sprint |
| `create_sprint(name, ...)` | Create new sprint |
| `move_issues_to_sprint(keys, id)` | Move issues to sprint |
| `start_sprint(id, ...)` | Start a sprint |
| `close_sprint(id)` | Close/complete a sprint |

### Field Methods

| Method | Description |
|--------|-------------|
| `add_labels(key, labels)` | Add labels to issue |
| `remove_labels(key, labels)` | Remove labels from issue |
| `set_story_points(key, points)` | Set story points |
| `update_issue(key, fields)` | Update any issue fields |

## Jira API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /rest/api/3/search` | Search issues (JQL) |
| `GET /rest/api/3/issue/{key}` | Get issue details |
| `POST /rest/api/3/issue` | Create new issue |
| `PUT /rest/api/3/issue/{key}` | Update issue |
| `POST /rest/api/3/issue/{key}/comment` | Add comment |
| `GET /rest/api/3/issue/{key}/transitions` | Get available transitions |
| `POST /rest/api/3/issue/{key}/transitions` | Transition issue |
| `POST /rest/api/3/issueLink` | Create issue link |
| `GET /rest/api/3/issueLinkType` | Get link types |
| `POST /rest/api/3/issue/bulk` | Bulk create issues |
| `GET /rest/agile/1.0/board` | List boards |
| `GET /rest/agile/1.0/board/{id}/sprint` | Get sprints |
| `POST /rest/agile/1.0/sprint` | Create sprint |
| `POST /rest/agile/1.0/sprint/{id}/issue` | Add issue to sprint |
| `PUT /rest/agile/1.0/sprint/{id}` | Update sprint |

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

### "Epic Link field not found"

For classic Jira projects, the Epic Link field name varies. RedGit auto-discovers it, but you can also set it manually:

```yaml
integrations:
  jira:
    epic_link_field: customfield_10014
```

### "Bulk operation failed"

Bulk operations may fail if:
1. Rate limit exceeded (100 req/min) - RedGit handles this with batching
2. Some issues have validation errors - check individual issue data
3. Permissions issue - verify your API token has write access

## See Also

- [Integrations Overview](../integrations.md)
- [Scout Integration](scout.md) - AI-powered project planning with Jira sync
- [GitHub Integration](github.md)
