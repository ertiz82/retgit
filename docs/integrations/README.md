# Integrations

RedGit supports various integrations for task management, code hosting, and more. Integrations can be built-in or custom.

## Available Integrations

### Task Management
- **[Jira](jira.md)** - Atlassian Jira Cloud with Scrum/Kanban support
- *Linear* - Coming soon
- *Asana* - Coming soon

### Code Hosting
- **[GitHub](github.md)** - GitHub pull requests and issues

### Analysis
- **[Scout](scout.md)** - AI-powered code analysis

## Quick Start

```bash
# List available integrations
rg integration list

# Install an integration
rg integration install jira

# Set as active
rg integration use jira
```

## Custom Integrations

You can create your own integrations for internal tools or unsupported platforms.

**[Custom Integration Guide](custom.md)** - Learn how to build custom integrations

### Quick Example

```python
# .redgit/integrations/my_tracker.py
from redgit.integrations.base import TaskManagementBase, IntegrationType, Issue

class MyTrackerIntegration(TaskManagementBase):
    name = "my_tracker"
    integration_type = IntegrationType.TASK_MANAGEMENT

    def setup(self, config: dict):
        self.api_url = config.get("api_url")
        self.enabled = bool(self.api_url)

    def get_my_active_issues(self):
        # Fetch issues from your API
        return []
```

## Integration Types

| Type | Purpose | Example |
|------|---------|---------|
| Task Management | Issue tracking | Jira, Linear |
| Code Hosting | Git hosting, PRs | GitHub, GitLab |
| Notification | Alerts, messages | Slack, Discord |
| Analysis | Code analysis | Scout |

## Configuration

All integrations are configured in `.redgit/config.yaml`:

```yaml
# Set active integrations by type
active:
  task_management: jira
  code_hosting: github
  analysis: scout

# Integration-specific settings
integrations:
  jira:
    enabled: true
    site: https://company.atlassian.net
    email: dev@company.com
    project_key: PROJ

  github:
    enabled: true
    owner: username
    repo: my-repo
```

## Environment Variables

Sensitive data (API keys, tokens) can be stored in environment variables:

| Integration | Variable |
|-------------|----------|
| Jira | `JIRA_API_TOKEN` |
| GitHub | `GITHUB_TOKEN` |
| Scout | `SCOUT_API_KEY` |

## Commands

```bash
# List all integrations
rg integration list

# Install with interactive wizard
rg integration install <name>

# Enable/disable
rg integration add <name>
rg integration remove <name>

# Set active for type
rg integration use <name>

# Integration-specific commands
rg jira list          # List Jira issues
rg jira create        # Create Jira issue
rg github pr          # Create GitHub PR
```