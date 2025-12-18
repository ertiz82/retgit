# RedGit Tap

**[RedGit Tap](https://github.com/ertiz82/redgit-tap)** is the official repository for community integrations and plugins.

---

## Overview

RedGit Tap provides all integrations for RedGit. These include:

- **Task Management**: Jira, Linear, Notion, Asana, Trello
- **Code Hosting**: GitHub, GitLab, Bitbucket, Azure Repos
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins, CircleCI
- **Notifications**: Slack, Discord, Telegram, MS Teams
- **Code Quality**: SonarQube, Snyk, Codecov, Codacy

---

## Installation

### Install from Official Tap

```bash
# Install an integration
rg install slack
rg install linear
rg install sonarqube

# Install a plugin
rg install plugin:laravel
rg install plugin:changelog

# Install specific version
rg install slack@v1.0.0

# List available integrations
rg tap list
```

### Install from Custom Tap

```bash
# Install from a custom tap (auto-adds tap first)
rg install myorg/my-tap jira
rg install myorg/my-tap plugin:myplugin

# Skip configuration wizard
rg install myorg/my-tap slack --no-configure
```

### Check Installed

```bash
rg integration status
```

---

## Available Integrations

### Task Management

| Name | Description |
|------|-------------|
| `jira` | Jira Cloud/Server with Scrum & Kanban support |
| `linear` | Modern issue tracking with cycles and projects |
| `notion` | Use Notion databases as task boards |
| `asana` | Project and task management |
| `trello` | Kanban board task management |

### Notifications

| Name | Description |
|------|-------------|
| `slack` | Send notifications to Slack channels |
| `discord` | Send notifications via Discord webhooks |
| `telegram` | Send notifications via Telegram Bot API |
| `msteams` | Send notifications to Microsoft Teams |
| `mattermost` | Send notifications to Mattermost channels |
| `rocketchat` | Send notifications to Rocket.Chat |
| `zulip` | Send notifications to Zulip streams |
| `whatsapp` | Send notifications via WhatsApp Business API |

### Code Hosting

| Name | Description |
|------|-------------|
| `github` | GitHub PRs, branches, repository management |
| `gitlab` | GitLab MRs, branches, self-hosted support |
| `bitbucket` | Bitbucket PRs, workspaces, branches |
| `codecommit` | AWS CodeCommit PRs and repository management |
| `azure-repos` | Azure Repos PRs and repository management |

### CI/CD

| Name | Description |
|------|-------------|
| `github-actions` | Manage workflows, trigger runs, view logs |
| `gitlab-ci` | Manage pipelines, trigger jobs |
| `jenkins` | Manage jobs, trigger builds |
| `circleci` | Manage pipelines, trigger workflows |
| `travis-ci` | Manage builds, trigger jobs |
| `azure-pipelines` | Manage Azure DevOps pipelines |
| `bitbucket-pipelines` | Manage Bitbucket pipelines |
| `drone-ci` | Manage Drone builds and deployments |

### Code Quality

| Name | Description |
|------|-------------|
| `sonarqube` | Code quality with quality gates |
| `codeclimate` | Maintainability and test coverage |
| `codacy` | Automated code review and security |
| `snyk` | Security vulnerability scanning |
| `dependabot` | Automated dependency updates |
| `renovate` | Automated dependency updates |
| `codecov` | Code coverage reporting |
| `coveralls` | Coverage tracking |

---

## Quick Start Examples

### Slack Notifications

```bash
# Install
rg install slack

# Configure in .redgit/config.yaml
# integrations:
#   slack:
#     webhook_url: https://hooks.slack.com/services/xxx
#
# active:
#   notification: slack
```

### Linear Task Management

```bash
# Install
rg install linear

# Configure
# integrations:
#   linear:
#     api_key: lin_api_xxx
#     team_id: your-team-id
#
# active:
#   task_management: linear
```

### SonarQube Code Quality

```bash
# Install
rg install sonarqube

# Set environment variable
export SONAR_TOKEN="your-token"

# Configure
# integrations:
#   sonarqube:
#     host: https://sonarcloud.io
#     project_key: my-project
#
# active:
#   code_quality: sonarqube
```

---

## Configuration

After installation, integrations are configured in `.redgit/config.yaml`:

```yaml
# Active integrations by type
active:
  task_management: linear
  code_hosting: github
  ci_cd: github-actions
  notification: slack
  code_quality: sonarqube

# Integration-specific settings
integrations:
  linear:
    api_key: ${LINEAR_API_KEY}
    team_id: your-team-id

  slack:
    webhook_url: https://hooks.slack.com/services/xxx
    channel: "#dev-notifications"

  sonarqube:
    host: https://sonarcloud.io
    project_key: my-project
```

---

## Environment Variables

Store sensitive data in environment variables:

| Integration | Variable |
|-------------|----------|
| Jira | `JIRA_API_TOKEN` |
| Linear | `LINEAR_API_KEY` |
| GitHub | `GITHUB_TOKEN` |
| GitLab | `GITLAB_TOKEN` |
| Slack | `SLACK_WEBHOOK_URL` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Telegram | `TELEGRAM_BOT_TOKEN` |
| SonarQube | `SONAR_TOKEN` |
| Snyk | `SNYK_TOKEN` |
| Codecov | `CODECOV_TOKEN` |

---

## Creating Custom Tap

You can create your own tap for internal integrations and plugins. Use the official template to get started:

**Template Repository**: [github.com/ertiz82/redgit-tap-template](https://github.com/ertiz82/redgit-tap-template)

```bash
# Fork or clone the template
gh repo clone ertiz82/redgit-tap-template my-tap

# Install from your custom tap
rg install myorg/my-tap my-integration
rg install myorg/my-tap plugin:my-plugin
```

See the [Custom Integration Guide](integrations/custom.md) for details on creating integrations.

### Integration Structure

```
integrations/my-integration/
├── __init__.py          # Integration class (required)
├── commands.py          # CLI commands (optional)
├── install_schema.json  # Installation wizard (optional)
└── README.md            # Documentation
```

### Example

```python
from redgit.integrations.base import NotificationBase, IntegrationType

class MyNotification(NotificationBase):
    name = "my-notification"
    integration_type = IntegrationType.NOTIFICATION

    def setup(self, config: dict):
        self.webhook = config.get("webhook_url")
        self.enabled = bool(self.webhook)

    def send_message(self, message: str, channel: str = None) -> bool:
        # Send notification
        return True
```

---

## Contributing

Want to add an integration to RedGit Tap?

1. Fork [github.com/ertiz82/redgit-tap](https://github.com/ertiz82/redgit-tap)
2. Create your integration
3. Update `index.json`
4. Submit a pull request

---

## Links

- **RedGit Tap Repository**: [github.com/ertiz82/redgit-tap](https://github.com/ertiz82/redgit-tap)
- **Main RedGit Repository**: [github.com/ertiz82/redgit](https://github.com/ertiz82/redgit)
- **Custom Integration Guide**: [integrations/custom.md](integrations/custom.md)