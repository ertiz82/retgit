# Integrations

RedGit supports various integrations for task management and code hosting platforms.

> **Looking for more integrations?** Check out **[RedGit Tap](https://github.com/ertiz82/redgit-tap)** - the official repository with 30+ community integrations including Linear, Notion, Asana, Trello, Telegram, MS Teams, and more.

## Available Integrations

| Integration | Type | Status | Documentation |
|-------------|------|--------|---------------|
| Jira | Task Management | ✅ Available | [jira.md](jira.md) |
| Scout | AI Project Planning | ✅ Available | [scout.md](scout.md) |
| GitHub | Code Hosting | ✅ Available | [github.md](github.md) |
| Linear | Task Management | ✅ Available | - |
| GitLab | Code Hosting | ✅ Available | - |
| Bitbucket | Code Hosting | ✅ Available | - |
| GitHub Actions | CI/CD | ✅ Available | - |
| GitLab CI | CI/CD | ✅ Available | - |
| Jenkins | CI/CD | ✅ Available | - |
| CircleCI | CI/CD | ✅ Available | - |
| Travis CI | CI/CD | ✅ Available | - |
| Azure Pipelines | CI/CD | ✅ Available | - |
| Bitbucket Pipelines | CI/CD | ✅ Available | - |
| Drone CI | CI/CD | ✅ Available | - |
| Slack | Notifications | ✅ Available | - |
| Discord | Notifications | ✅ Available | - |
| SonarQube | Code Quality | ✅ Available | - |
| CodeClimate | Code Quality | ✅ Available | - |
| Codacy | Code Quality | ✅ Available | - |
| Snyk | Code Quality | ✅ Available | - |
| Dependabot | Code Quality | ✅ Available | - |
| Renovate | Code Quality | ✅ Available | - |
| Codecov | Code Quality | ✅ Available | - |
| Coveralls | Code Quality | ✅ Available | - |

## Quick Start

### Install an Integration

```bash
rg integration install jira
rg integration install github
```

### Check Status

```bash
rg integration status
```

### List Available

```bash
rg integration list
```

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Integration Types                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TaskManagementBase                                         │
│  ├── JiraIntegration                                        │
│  ├── LinearIntegration                                      │
│  ├── NotionIntegration                                      │
│  ├── AsanaIntegration                                       │
│  └── TrelloIntegration                                      │
│                                                             │
│  CodeHostingBase                                            │
│  ├── GitHubIntegration                                      │
│  ├── GitLabIntegration                                      │
│  ├── BitbucketIntegration                                   │
│  ├── AzureReposIntegration                                  │
│  └── CodeCommitIntegration                                  │
│                                                             │
│  CICDBase                                                   │
│  ├── GitHubActionsIntegration                               │
│  ├── GitLabCIIntegration                                    │
│  ├── JenkinsIntegration                                     │
│  ├── CircleCIIntegration                                    │
│  ├── TravisCIIntegration                                    │
│  ├── AzurePipelinesIntegration                              │
│  ├── BitbucketPipelinesIntegration                          │
│  └── DroneCIIntegration                                     │
│                                                             │
│  NotificationBase                                           │
│  ├── SlackIntegration                                       │
│  ├── DiscordIntegration                                     │
│  ├── TelegramIntegration                                    │
│  ├── MSTeamsIntegration                                     │
│  └── MattermostIntegration                                  │
│                                                             │
│  AIIntegrationBase                                          │
│  └── ScoutIntegration (AI project planning & team mgmt)     │
│                                                             │
│  CodeQualityBase                                            │
│  ├── SonarQubeIntegration                                   │
│  ├── CodeClimateIntegration                                 │
│  ├── CodacyIntegration                                      │
│  ├── SnykIntegration                                        │
│  ├── DependabotIntegration                                  │
│  ├── RenovateIntegration                                    │
│  ├── CodecovIntegration                                     │
│  └── CoverallsIntegration                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Integrations are configured in `.redgit/config.yaml`:

```yaml
active:
  task_management: jira
  code_hosting: github
  ci_cd: github-actions
  notification: slack

integrations:
  jira:
    site: https://your-company.atlassian.net
    email: developer@company.com
    project_key: PROJ

  github:
    owner: your-username
    repo: your-repo

  github-actions:
    owner: your-username
    repo: your-repo

  slack:
    webhook_url: https://hooks.slack.com/...
```

## Environment Variables

Sensitive data should be stored in environment variables:

| Integration | Environment Variable |
|-------------|---------------------|
| Jira | `JIRA_API_TOKEN` |
| GitHub | `GITHUB_TOKEN` |
| GitHub Actions | `GITHUB_TOKEN` |
| GitLab CI | `GITLAB_TOKEN` |
| Jenkins | `JENKINS_API_TOKEN` |
| CircleCI | `CIRCLECI_TOKEN` |
| Travis CI | `TRAVIS_TOKEN` |
| Azure Pipelines | `AZURE_DEVOPS_PAT` |
| Drone CI | `DRONE_TOKEN` |
| Scout | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` |

---

## Detailed Documentation

- **[Jira Integration](jira.md)** - Full Jira Cloud integration with Scrum/Kanban support
- **[Scout Integration](scout.md)** - AI-powered project planning, team management, and task sync
- **[GitHub Integration](github.md)** - GitHub integration for PRs and repository operations

---

## Jira Integration

Full-featured Jira Cloud integration with Scrum and Kanban support.

### Installation

```bash
rg integration install jira
```

### Configuration

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

### Environment Variables

```bash
# Required
export JIRA_API_TOKEN="your-api-token"
```

### API Token Setup

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a descriptive label (e.g., "RedGit")
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
# redgit/integrations/linear.py

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
# redgit/integrations/gitlab.py

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

Add to `redgit/integrations/registry.py`:

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
   Each project can have different integration settings in `.redgit/config.yaml`

4. **Enable only what you need**
   ```yaml
   active:
     task_management: jira
     code_hosting: none  # Disable if not needed
   ```

---

## Community Integrations (RedGit Tap)

For additional integrations not listed here, visit **[RedGit Tap](https://github.com/ertiz82/redgit-tap)** - the official community integration repository with 30+ integrations.

```bash
# Install from RedGit Tap
rg install linear
rg install notion
rg install telegram
rg install sonarqube
```

---

## CI/CD Integrations

RedGit supports various CI/CD platforms to manage pipelines directly from the command line.

### Available CI/CD Integrations

| Integration | Description |
|-------------|-------------|
| `github-actions` | GitHub Actions workflows |
| `gitlab-ci` | GitLab CI/CD pipelines |
| `jenkins` | Jenkins jobs and builds |
| `circleci` | CircleCI pipelines |
| `travis-ci` | Travis CI builds |
| `azure-pipelines` | Azure DevOps pipelines |
| `bitbucket-pipelines` | Bitbucket Pipelines |
| `drone-ci` | Drone CI builds |

### Installation

```bash
# Install a CI/CD integration
rg install github-actions
rg install gitlab-ci
rg install jenkins
```

### GitHub Actions

```yaml
# .redgit/config.yaml
active:
  ci_cd: github-actions

integrations:
  github-actions:
    owner: your-username
    repo: your-repo
    # token: stored in GITHUB_TOKEN env var
```

### GitLab CI

```yaml
# .redgit/config.yaml
active:
  ci_cd: gitlab-ci

integrations:
  gitlab-ci:
    url: https://gitlab.com        # or self-hosted URL
    project_id: "12345"            # or "group/project"
    # token: stored in GITLAB_TOKEN env var
```

### Jenkins

```yaml
# .redgit/config.yaml
active:
  ci_cd: jenkins

integrations:
  jenkins:
    url: https://jenkins.company.com
    username: your-username
    job_name: my-pipeline          # Optional, auto-detects from repo
    # token: stored in JENKINS_API_TOKEN env var
```

### CircleCI

```yaml
# .redgit/config.yaml
active:
  ci_cd: circleci

integrations:
  circleci:
    project_slug: gh/owner/repo    # or bb/owner/repo for Bitbucket
    # token: stored in CIRCLECI_TOKEN env var
```

### Drone CI

```yaml
# .redgit/config.yaml
active:
  ci_cd: drone-ci

integrations:
  drone-ci:
    server: https://drone.company.com
    owner: your-username
    repo: your-repo
    # token: stored in DRONE_TOKEN env var
```

### CI/CD Commands

```bash
# Show CI/CD status overview
rg ci status

# List recent pipelines/builds
rg ci pipelines
rg ci pipelines --branch main --limit 20
rg ci pipelines --status failed

# Show pipeline details
rg ci pipeline 12345

# List jobs/stages in a pipeline
rg ci jobs 12345

# Trigger a new pipeline
rg ci trigger
rg ci trigger --branch main
rg ci trigger --workflow build --param KEY=VALUE

# Watch pipeline until completion
rg ci watch 12345
rg ci watch          # Watch latest pipeline on current branch

# Cancel/Retry pipelines
rg ci cancel 12345
rg ci retry 12345

# View build logs
rg ci logs 12345
rg ci logs 12345 --job build --tail 100
```

### Integration with Push

CI/CD pipelines can be triggered automatically after `rg push`:

```bash
# Push and trigger CI/CD pipeline
rg push --ci

# Push and wait for pipeline to complete
rg push --ci --wait-ci

# Push without triggering CI (even if integration is active)
rg push --no-ci
```

When `--wait-ci` is used:
- RedGit will poll the pipeline status every 10 seconds
- Maximum wait time is 10 minutes
- If a notification integration is configured, you'll be notified on completion

### Creating CI/CD Integrations

```python
# redgit/integrations/my_cicd.py

from .base import CICDBase, PipelineRun, PipelineJob, IntegrationType

class MyCICDIntegration(CICDBase):
    name = "my-cicd"
    integration_type = IntegrationType.CI_CD

    def setup(self, config: dict):
        self.url = config.get("url")
        self.token = config.get("token") or os.getenv("MY_CICD_TOKEN")
        self.enabled = bool(self.url and self.token)

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: dict = None
    ) -> Optional[PipelineRun]:
        """Trigger a new pipeline run."""
        # Implement API call
        return PipelineRun(
            name="build-123",
            status="running",
            branch=branch,
            url="https://..."
        )

    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineRun]:
        """Get status of a specific pipeline."""
        # Implement API call
        pass

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List recent pipeline runs."""
        # Implement API call
        pass

    def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline."""
        # Implement API call
        pass

    def get_pipeline_jobs(self, pipeline_id: str) -> List[PipelineJob]:
        """Get jobs/stages for a pipeline."""
        # Implement API call
        pass

    def get_build_logs(
        self,
        pipeline_id: str,
        job_id: str = None,
        stage: int = None,
        step: int = None
    ) -> Optional[str]:
        """Get build logs."""
        # Implement API call
        pass
```

### PipelineRun Dataclass

```python
@dataclass
class PipelineRun:
    name: str               # Pipeline ID or number
    status: str             # running, success, failed, pending, etc.
    branch: str = None      # Branch name
    commit_sha: str = None  # Commit SHA
    url: str = None         # Web URL to pipeline
    duration: int = None    # Duration in seconds
    trigger: str = None     # What triggered: push, manual, schedule, etc.
```

### PipelineJob Dataclass

```python
@dataclass
class PipelineJob:
    id: str                 # Job ID
    name: str               # Job name
    status: str             # running, success, failed, etc.
    duration: int = None    # Duration in seconds
    url: str = None         # Web URL to job
```

---

## Notification Integrations

RedGit supports notification integrations to keep you informed about important events.

### Available Notification Integrations

| Integration | Description |
|-------------|-------------|
| `slack` | Send notifications to Slack channels via webhooks |
| `discord` | Send notifications to Discord channels via webhooks |
| `telegram` | Send notifications via Telegram Bot API |
| `msteams` | Send notifications to Microsoft Teams |
| `mattermost` | Send notifications to Mattermost channels |
| `rocketchat` | Send notifications to Rocket.Chat |
| `zulip` | Send notifications to Zulip streams |
| `whatsapp` | Send notifications via WhatsApp Business API |

### Installation

```bash
# Install a notification integration
rg install slack
rg install discord
rg install telegram
```

### Configuration

```yaml
# .redgit/config.yaml
active:
  notification: slack

integrations:
  slack:
    webhook_url: https://hooks.slack.com/services/xxx
    channel: "#dev-notifications"  # Optional

  discord:
    webhook_url: https://discord.com/api/webhooks/xxx

  telegram:
    bot_token: "123456:ABC..."  # or TELEGRAM_BOT_TOKEN env var
    chat_id: "-1001234567890"
```

### Automatic Notification Points

When a notification integration is active, RedGit automatically sends notifications for:

| Event | Command | Notification |
|-------|---------|--------------|
| Push completed | `rg push` | 📤 Pushed `branch` to remote |
| PR created | `rg push --pr` | 🔀 PR created for `branch` |
| Issue completed | `rg push --complete` | ✅ Issue PROJ-123 marked as Done |
| CI/CD success | `rg push --ci --wait-ci` | ✅ Pipeline completed successfully |
| CI/CD failure | `rg push --ci --wait-ci` | ❌ Pipeline failed |
| Issue created | `rg propose` | 🆕 Issue created: PROJ-123 |
| Session complete | `rg propose` | 📦 Session complete: 3 commits, 2 issues |
| Commit created | `rg propose --task` | 📝 Committed to `branch` (PROJ-123) |

### Manual Notifications

```bash
# Send a custom notification
rg notify "Deployment complete!"
rg notify "Build #123 passed" --channel "#builds"
```

### Creating Notification Integrations

```python
# redgit/integrations/my_notification.py

from .base import NotificationBase, IntegrationType

class MyNotificationIntegration(NotificationBase):
    name = "my-notification"
    integration_type = IntegrationType.NOTIFICATION

    def setup(self, config: dict):
        self.webhook_url = config.get("webhook_url")
        self.enabled = bool(self.webhook_url)

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a notification message."""
        import requests

        payload = {"text": message}
        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(self.webhook_url, json=payload)
            return response.ok
        except Exception:
            return False
```

### Using Notifications in Custom Integrations

When creating custom integrations that should send notifications, use the `get_notification` helper:

```python
from redgit.integrations.registry import get_notification

def my_custom_function(config: dict, event: str, details: str):
    # Do your work...

    # Send notification if available
    notification = get_notification(config)
    if notification and notification.enabled:
        notification.send_message(f"{event}: {details}")
```

This ensures notifications are sent only when a notification integration is configured and active.

---

## Code Quality Integrations

RedGit supports code quality integrations for automated code review, security scanning, and coverage reporting.

### Available Code Quality Integrations

| Integration | Description |
|-------------|-------------|
| `sonarqube` | SonarQube/SonarCloud code quality analysis with quality gates |
| `codeclimate` | CodeClimate maintainability and test coverage |
| `codacy` | Codacy automated code review and security analysis |
| `snyk` | Snyk security vulnerability scanning |
| `dependabot` | GitHub Dependabot for automated dependency updates |
| `renovate` | Renovate automated dependency updates |
| `codecov` | Codecov code coverage reporting |
| `coveralls` | Coveralls coverage tracking |

### Installation

```bash
# Install a code quality integration
rg tap install sonarqube
rg tap install snyk
rg tap install codecov
```

### SonarQube/SonarCloud

```yaml
# .redgit/config.yaml
active:
  code_quality: sonarqube

integrations:
  sonarqube:
    host: https://sonarcloud.io    # or self-hosted URL
    project_key: my-project
    organization: my-org           # For SonarCloud
    # token: stored in SONAR_TOKEN env var
```

Environment variables:
```bash
export SONAR_TOKEN="your-sonar-token"
export SONAR_HOST_URL="https://sonarcloud.io"  # optional
export SONAR_PROJECT_KEY="my-project"          # optional
```

### Snyk

```yaml
# .redgit/config.yaml
active:
  code_quality: snyk

integrations:
  snyk:
    org_id: your-org-id
    project_id: your-project-id    # Optional
    # token: stored in SNYK_TOKEN env var
```

Environment variables:
```bash
export SNYK_TOKEN="your-snyk-token"
export SNYK_ORG_ID="your-org-id"
```

### Codecov

```yaml
# .redgit/config.yaml
active:
  code_quality: codecov

integrations:
  codecov:
    owner: your-username
    repo: your-repo
    service: github               # github, gitlab, bitbucket
    # token: stored in CODECOV_TOKEN env var
```

### Dependabot / Renovate

These integrations work with GitHub and track dependency update PRs:

```yaml
# .redgit/config.yaml
integrations:
  dependabot:
    owner: your-username
    repo: your-repo
    # Uses GITHUB_TOKEN env var

  renovate:
    owner: your-username
    repo: your-repo
    renovate_bot: renovate[bot]   # Bot username
```

### Notification Events

Code quality integrations emit the following notification events:

| Integration | Events |
|-------------|--------|
| SonarQube | `quality_gate_passed`, `quality_gate_failed`, `new_bugs`, `new_vulnerabilities`, `coverage_decreased` |
| CodeClimate | `maintainability_changed`, `coverage_changed`, `new_issues`, `technical_debt_increased` |
| Codacy | `grade_changed`, `quality_gate_failed`, `security_issue_found`, `new_issues` |
| Snyk | `critical_vulnerability`, `high_vulnerability`, `new_vulnerabilities`, `vulnerability_fixed`, `license_issue` |
| Dependabot | `security_alert`, `pr_created`, `pr_merged`, `update_available` |
| Renovate | `pr_created`, `pr_merged`, `major_update`, `security_update`, `config_error` |
| Codecov | `coverage_decreased`, `coverage_increased`, `target_missed`, `new_uncovered_lines` |
| Coveralls | `coverage_decreased`, `coverage_increased`, `build_passed`, `build_failed` |

### Creating Code Quality Integrations

```python
# redgit/integrations/my_quality.py

from .base import CodeQualityBase, QualityReport, SecurityIssue, CoverageReport, IntegrationType

class MyQualityIntegration(CodeQualityBase):
    name = "my-quality"
    integration_type = IntegrationType.CODE_QUALITY

    # Define notification events
    notification_events = {
        "quality_gate_passed": {
            "description": "Quality gate passed",
            "default": True
        },
        "quality_gate_failed": {
            "description": "Quality gate failed",
            "default": True
        },
    }

    def setup(self, config: dict):
        self.token = config.get("token") or os.getenv("MY_QUALITY_TOKEN")
        self.project_id = config.get("project_id")
        self.enabled = bool(self.token and self.project_id)

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get quality status for a branch or commit."""
        # Implement API call
        return QualityReport(
            id=self.project_id,
            status="passed",
            branch=branch,
            bugs=5,
            vulnerabilities=0,
            coverage=85.5,
            quality_gate_status="passed"
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project quality metrics."""
        # Implement API call
        pass

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """Get security vulnerabilities."""
        # Implement API call
        pass

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """Get code coverage report."""
        # Implement API call
        pass
```

### QualityReport Dataclass

```python
@dataclass
class QualityReport:
    id: str
    status: str                    # "passed", "failed", "warning", "pending"
    branch: str = None
    commit_sha: str = None
    url: str = None
    analyzed_at: str = None
    # Quality metrics
    bugs: int = None
    vulnerabilities: int = None
    code_smells: int = None
    coverage: float = None         # percentage (0-100)
    duplications: float = None     # percentage
    technical_debt: str = None     # e.g., "2h 30min"
    # Quality gate
    quality_gate_status: str = None  # "passed", "failed"
    quality_gate_details: Dict = None
```

### SecurityIssue Dataclass

```python
@dataclass
class SecurityIssue:
    id: str
    severity: str                  # "critical", "high", "medium", "low", "info"
    title: str
    description: str = None
    package: str = None            # affected package/dependency
    version: str = None            # affected version
    fixed_in: str = None           # version with fix
    cve: str = None                # CVE identifier
    cwe: str = None                # CWE identifier
    url: str = None
    file_path: str = None
    line_number: int = None
```

### CoverageReport Dataclass

```python
@dataclass
class CoverageReport:
    id: str
    commit_sha: str = None
    branch: str = None
    url: str = None
    # Coverage metrics
    line_coverage: float = None      # percentage
    branch_coverage: float = None    # percentage
    function_coverage: float = None  # percentage
    lines_covered: int = None
    lines_total: int = None
    # Comparison
    coverage_change: float = None    # delta from base
    base_coverage: float = None
```