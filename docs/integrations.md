# Integrations Guide

RetGit supports multiple integration types:

- **Task Management**: Jira, Linear (planned), Asana (planned)
- **Code Hosting**: GitHub, GitLab (planned), Bitbucket (planned)
- **Notifications**: Slack (planned), Discord (planned)

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Integration Types                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TaskManagementBase                                         │
│  ├── JiraIntegration                                        │
│  ├── LinearIntegration (planned)                            │
│  └── AsanaIntegration (planned)                             │
│                                                             │
│  CodeHostingBase                                            │
│  ├── GitHubIntegration                                      │
│  ├── GitLabIntegration (planned)                            │
│  └── BitbucketIntegration (planned)                         │
│                                                             │
│  NotificationBase                                           │
│  ├── SlackIntegration (planned)                             │
│  └── DiscordIntegration (planned)                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Jira Integration

Full-featured Jira Cloud integration with Scrum and Kanban support.

### Installation

```bash
rg integration install jira
```

### Configuration

```yaml
# .retgit/config.yaml
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

### Environment Variables

```bash
# Required
export JIRA_API_TOKEN="your-api-token"
```

### API Token Setup

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a descriptive label (e.g., "RetGit")
4. Copy the token
5. Store as `JIRA_API_TOKEN` environment variable

### Features

#### Issue Fetching
```python
# Fetches issues where:
# - Assigned to current user
# - Status is "To Do", "In Progress", "Open", or "In Development"
# - In current sprint (for Scrum boards)
```

#### Status Transitions
```
To Do ──► In Progress ──► Done
         (on commit)      (on push)
```

#### Branch Naming
Default pattern: `feature/{issue_key}-{description}`

Example: `feature/PROJ-123-add-user-authentication`

#### Sprint Support
For Scrum boards:
- Auto-detects active sprint
- New issues are added to active sprint
- Shows sprint info in `rg propose`

### Jira API Endpoints Used

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

---

## GitHub Integration

GitHub integration for repository operations and PR creation.

### Installation

```bash
rg integration install github
```

### Configuration

```yaml
# .retgit/config.yaml
active:
  code_hosting: github

integrations:
  github:
    owner: your-username
    repo: your-repo
    default_base: main
    auto_pr: false
```

### Environment Variables

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

### Token Setup

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (Full control of private repositories)
4. Copy and store as `GITHUB_TOKEN`

### Features

#### Pull Request Creation
```bash
rg push --pr
```

Creates a PR with:
- Title: Issue key + branch description
- Body: References to linked issues
- Base: Configured default branch

---

## Creating Custom Integrations

### Task Management Integration

```python
# retgit/integrations/linear.py

from .base import TaskManagementBase, Issue, Sprint, IntegrationType

class LinearIntegration(TaskManagementBase):
    name = "linear"
    integration_type = IntegrationType.TASK_MANAGEMENT

    def setup(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("LINEAR_API_KEY")
        self.team_id = config.get("team_id")
        self.enabled = bool(self.api_key and self.team_id)

    def get_my_active_issues(self) -> List[Issue]:
        # Implement Linear GraphQL API call
        pass

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        # Implement
        pass

    def create_issue(self, summary, description, issue_type, story_points) -> Optional[str]:
        # Implement
        pass

    def add_comment(self, issue_key: str, comment: str) -> bool:
        # Implement
        pass

    def transition_issue(self, issue_key: str, status: str) -> bool:
        # Implement
        pass

    def format_branch_name(self, issue_key: str, description: str) -> str:
        return f"feature/{issue_key}-{description}"
```

### Code Hosting Integration

```python
# retgit/integrations/gitlab.py

from .base import CodeHostingBase, IntegrationType

class GitlabIntegration(CodeHostingBase):
    name = "gitlab"
    integration_type = IntegrationType.CODE_HOSTING

    def setup(self, config: dict):
        self.project_id = config.get("project_id")
        self.token = config.get("token") or os.getenv("GITLAB_TOKEN")
        self.enabled = bool(self.project_id and self.token)

    def create_pull_request(self, title, body, head_branch, base_branch) -> Optional[str]:
        # Implement GitLab Merge Request API
        pass

    def push_branch(self, branch_name: str) -> bool:
        # Implement
        pass
```

### Register New Integration

Add to `retgit/integrations/registry.py`:

```python
BUILTIN_INTEGRATIONS = {
    "jira": IntegrationType.TASK_MANAGEMENT,
    "github": IntegrationType.CODE_HOSTING,
    "linear": IntegrationType.TASK_MANAGEMENT,  # Add new
    "gitlab": IntegrationType.CODE_HOSTING,     # Add new
}
```

---

## Integration Config Schema

Integration install wizards use `install_schemas.json`:

```json
{
  "integrations": {
    "linear": {
      "name": "Linear",
      "description": "Linear integration for issue tracking",
      "fields": [
        {
          "key": "api_key",
          "prompt": "Linear API Key",
          "type": "secret",
          "env_var": "LINEAR_API_KEY",
          "required": true
        },
        {
          "key": "team_id",
          "prompt": "Team ID",
          "type": "text",
          "required": true
        }
      ]
    }
  }
}
```

### Field Types

| Type | Description |
|------|-------------|
| `text` | Plain text input |
| `secret` | Hidden input, stored in env var |
| `choice` | Select from predefined options |
| `confirm` | Yes/No boolean |

---

## Best Practices

1. **Always use environment variables for tokens**
   ```bash
   export JIRA_API_TOKEN="xxx"  # Good
   # token: xxx in config.yaml  # Bad
   ```

2. **Test connection before committing**
   ```bash
   rg integration status
   ```

3. **Use project-specific config**
   Each project can have different integration settings in `.retgit/config.yaml`

4. **Enable only what you need**
   ```yaml
   active:
     task_management: jira
     code_hosting: none  # Disable if not needed
   ```