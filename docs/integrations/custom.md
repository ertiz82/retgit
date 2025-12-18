# Custom Integrations

RedGit supports custom integrations that you can create for your own task management systems, code hosting platforms, or any other tools.

## Quick Start

The fastest way to create a custom integration:

```bash
# Scaffold a new integration
rg integration create my_tracker

# This creates:
# .redgit/integrations/my_tracker/
# ├── __init__.py          # Integration class
# ├── commands.py          # CLI commands
# ├── install_schema.json  # Installation wizard
# ├── README.md            # Documentation
# └── prompts/             # AI prompts (optional)
```

## Overview

Custom integrations are Python files placed in your project's `.redgit/integrations/` directory. RedGit automatically discovers and loads them alongside the built-in integrations.

## Directory Structure

```
your-project/
├── .redgit/
│   ├── config.yaml
│   └── integrations/
│       ├── my_tracker.py          # Single file integration
│       └── company_tools/         # Package integration
│           ├── __init__.py
│           └── commands.py        # Optional CLI commands
```

## Integration Types

RedGit supports four integration types:

| Type | Base Class | Purpose |
|------|------------|---------|
| `TASK_MANAGEMENT` | `TaskManagementBase` | Issue trackers (Jira, Linear, etc.) |
| `CODE_HOSTING` | `CodeHostingBase` | Git hosting (GitHub, GitLab, etc.) |
| `NOTIFICATION` | `NotificationBase` | Notifications (Slack, Discord, etc.) |
| `ANALYSIS` | `AnalysisBase` | Code analysis tools |

## Creating a Custom Integration

### Basic Structure

```python
# .redgit/integrations/my_tracker.py

from redgit.integrations.base import TaskManagementBase, IntegrationType, Issue

class MyTrackerIntegration(TaskManagementBase):
    """Custom task management integration."""

    name = "my_tracker"
    integration_type = IntegrationType.TASK_MANAGEMENT

    def setup(self, config: dict):
        """Initialize the integration with config values."""
        self.api_url = config.get("api_url", "")
        self.api_key = config.get("api_key", "")
        self.project_id = config.get("project_id", "")

        # Set enabled based on required fields
        self.enabled = bool(self.api_url and self.api_key and self.project_id)

    def get_my_active_issues(self):
        """Fetch active issues assigned to current user."""
        if not self.enabled:
            return []

        # Your API call logic here
        issues = []
        # ... fetch from your API ...

        return [
            Issue(
                key="TASK-123",
                summary="Task title",
                status="In Progress",
                assignee="user@example.com",
                issue_type="task"
            )
            for item in your_api_response
        ]

    def create_issue(self, summary: str, description: str = "", issue_type: str = "task", **kwargs):
        """Create a new issue."""
        if not self.enabled:
            return None

        # Your API call to create issue
        # Return the issue key (e.g., "TASK-124")
        return "TASK-124"

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Change issue status."""
        if not self.enabled:
            return False

        # Your API call to transition issue
        return True

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to an issue."""
        if not self.enabled:
            return False

        # Your API call to add comment
        return True
```

### The Issue Class

Use the `Issue` dataclass for returning issues:

```python
from redgit.integrations.base import Issue

issue = Issue(
    key="TASK-123",           # Unique identifier
    summary="Fix login bug",   # Issue title
    status="In Progress",      # Current status
    assignee="user@email.com", # Assigned user
    issue_type="bug",          # Type: task, story, bug, etc.
    url="https://..."          # Optional: link to issue
)
```

## Adding Install Schema

To enable `rg integration install my_tracker`, add an install schema:

```python
# .redgit/integrations/my_tracker.py

class MyTrackerIntegration(TaskManagementBase):
    # ... class definition ...

    # Install schema for interactive setup
    INSTALL_SCHEMA = {
        "name": "My Tracker",
        "description": "Custom task management integration",
        "fields": [
            {
                "key": "api_url",
                "prompt": "API URL",
                "type": "text",
                "required": True,
                "help": "Base URL for your tracker API"
            },
            {
                "key": "api_key",
                "prompt": "API Key",
                "type": "secret",
                "required": True,
                "env_var": "MY_TRACKER_API_KEY"
            },
            {
                "key": "project_id",
                "prompt": "Project ID",
                "type": "text",
                "required": True
            }
        ]
    }
```

### Field Types

| Type | Description |
|------|-------------|
| `text` | Plain text input |
| `secret` | Hidden input (for API keys, tokens) |
| `choice` | Selection from predefined options |
| `confirm` | Yes/No boolean |

## after_install Hook

Auto-detect settings during installation:

```python
class MyTrackerIntegration(TaskManagementBase):
    # ...

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Called after install wizard, before saving config."""
        import requests

        api_url = config_values.get("api_url", "")
        api_key = config_values.get("api_key", "")

        if api_url and api_key:
            # Auto-detect project settings
            try:
                response = requests.get(
                    f"{api_url}/api/settings",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.ok:
                    settings = response.json()
                    config_values["default_board"] = settings.get("default_board")
                    print(f"   ✓ Auto-detected board: {settings.get('default_board')}")
            except Exception:
                pass

        return config_values
```

## Adding CLI Commands

Create CLI commands for your integration:

```python
# .redgit/integrations/my_tracker/commands.py

import typer

my_tracker_app = typer.Typer(help="My Tracker commands")

@my_tracker_app.command("list")
def list_issues():
    """List all issues."""
    # Load integration and list issues
    typer.echo("Listing issues...")

@my_tracker_app.command("create")
def create_issue(title: str):
    """Create a new issue."""
    typer.echo(f"Creating issue: {title}")
```

Commands will be available as:
```bash
rg my_tracker list
rg my_tracker create "New feature"
```

## Configuration

After creating your integration, configure it in `.redgit/config.yaml`:

```yaml
active:
  task_management: my_tracker

integrations:
  my_tracker:
    enabled: true
    api_url: https://tracker.company.com
    api_key: your-api-key
    project_id: PROJECT-1
```

Or use the install wizard:
```bash
rg integration install my_tracker
```

## Complete Example: Linear Integration

Here's a more complete example for Linear:

```python
# .redgit/integrations/linear.py

import requests
from typing import List, Optional
from redgit.integrations.base import TaskManagementBase, IntegrationType, Issue

class LinearIntegration(TaskManagementBase):
    """Linear.app task management integration."""

    name = "linear"
    integration_type = IntegrationType.TASK_MANAGEMENT

    INSTALL_SCHEMA = {
        "name": "Linear",
        "description": "Linear.app issue tracking",
        "fields": [
            {
                "key": "api_key",
                "prompt": "API Key",
                "type": "secret",
                "required": True,
                "help": "Get from Linear Settings > API > Personal API keys",
                "env_var": "LINEAR_API_KEY"
            },
            {
                "key": "team_id",
                "prompt": "Team ID",
                "type": "text",
                "required": True,
                "help": "Your Linear team identifier"
            }
        ]
    }

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.team_id = ""
        self.api_url = "https://api.linear.app/graphql"
        self.session = None

    def setup(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.team_id = config.get("team_id", "")

        self.enabled = bool(self.api_key and self.team_id)

        if self.enabled:
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            })

    def _graphql(self, query: str, variables: dict = None):
        """Execute GraphQL query."""
        response = self.session.post(
            self.api_url,
            json={"query": query, "variables": variables or {}}
        )
        response.raise_for_status()
        return response.json()

    def get_my_active_issues(self) -> List[Issue]:
        if not self.enabled:
            return []

        query = """
        query MyIssues($teamId: String!) {
            issues(filter: {
                team: { id: { eq: $teamId } }
                assignee: { isMe: { eq: true } }
                state: { type: { in: ["started", "unstarted"] } }
            }) {
                nodes {
                    identifier
                    title
                    state { name }
                    assignee { email }
                    url
                }
            }
        }
        """

        try:
            result = self._graphql(query, {"teamId": self.team_id})
            issues = []

            for node in result.get("data", {}).get("issues", {}).get("nodes", []):
                issues.append(Issue(
                    key=node["identifier"],
                    summary=node["title"],
                    status=node["state"]["name"],
                    assignee=node.get("assignee", {}).get("email", ""),
                    issue_type="issue",
                    url=node.get("url")
                ))

            return issues
        except Exception:
            return []

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        **kwargs
    ) -> Optional[str]:
        if not self.enabled:
            return None

        query = """
        mutation CreateIssue($teamId: String!, $title: String!, $description: String) {
            issueCreate(input: {
                teamId: $teamId
                title: $title
                description: $description
            }) {
                issue {
                    identifier
                }
            }
        }
        """

        try:
            result = self._graphql(query, {
                "teamId": self.team_id,
                "title": summary,
                "description": description
            })
            return result["data"]["issueCreate"]["issue"]["identifier"]
        except Exception:
            return None

    def transition_issue(self, issue_key: str, status: str) -> bool:
        # Implementation for Linear state transition
        return True

    def add_comment(self, issue_key: str, comment: str) -> bool:
        # Implementation for adding comments
        return True

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Auto-detect team info after install."""
        import requests

        api_key = config_values.get("api_key", "")
        if not api_key:
            return config_values

        try:
            response = requests.post(
                "https://api.linear.app/graphql",
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json"
                },
                json={"query": "{ viewer { name email } }"}
            )
            if response.ok:
                data = response.json()
                viewer = data.get("data", {}).get("viewer", {})
                print(f"   ✓ Connected as: {viewer.get('name')} ({viewer.get('email')})")
        except Exception:
            pass

        return config_values
```

## Overriding Built-in Integrations

Custom integrations with the same name as built-in ones will override them. This allows you to customize behavior:

```python
# .redgit/integrations/jira.py
# This will override the built-in Jira integration

from redgit.integrations.jira import JiraIntegration as BaseJira

class JiraIntegration(BaseJira):
    """Custom Jira integration with company-specific logic."""

    def get_my_active_issues(self):
        # Add custom filtering
        issues = super().get_my_active_issues()
        return [i for i in issues if not i.summary.startswith("[IGNORE]")]
```

## Debugging

Enable debug output to troubleshoot your integration:

```python
def setup(self, config: dict):
    self.debug = config.get("debug", False)
    # ...

def get_my_active_issues(self):
    if self.debug:
        print(f"[DEBUG] Fetching issues from {self.api_url}")
    # ...
```

```yaml
integrations:
  my_tracker:
    enabled: true
    debug: true
```

## Best Practices

1. **Always check `self.enabled`** before making API calls
2. **Handle exceptions gracefully** - return empty lists or `None` on errors
3. **Use environment variables** for sensitive data (API keys)
4. **Implement `after_install`** to auto-detect settings when possible
5. **Follow naming conventions**: `{Name}Integration` class name
6. **Add helpful docstrings** for CLI discoverability

---

## Integration Prompts

Task management integrations can provide custom prompts for generating issue titles and descriptions. This allows:
- Localized issue content (e.g., Turkish, German, Spanish)
- Company-specific formatting
- Domain-specific terminology

### How Integration Prompts Work

When `rg propose --detailed` is used:
1. RedGit analyzes file diffs for each commit group
2. If integration has custom prompts, they're used to generate issue content
3. The LLM follows your prompts to create localized/customized issue titles and descriptions

### Prompt Priority

1. **User-exported prompts** (highest priority): `.redgit/prompts/integrations/{name}/`
2. **Built-in integration prompts**: Packaged with the integration
3. **RedGit default prompts** (fallback): Generic issue generation

### Adding Prompts to Your Integration

Create a `prompts/` directory in your integration:

```
.redgit/integrations/my_tracker/
├── __init__.py
├── commands.py
├── install_schema.json
└── prompts/
    ├── issue_title.md
    └── issue_description.md
```

#### issue_title.md

```markdown
Generate a clear, concise issue title in Turkish.

Requirements:
- Maximum 80 characters
- Use action verbs (Ekle, Düzelt, Güncelle, Kaldır)
- Be specific about what changed
- Don't include technical jargon

Examples:
- "Kullanıcı giriş formuna doğrulama ekle"
- "Ödeme sayfasındaki hata düzelt"
- "Dashboard performansını iyileştir"
```

#### issue_description.md

```markdown
Generate a detailed issue description in Turkish.

Structure:
1. **Özet**: One sentence summary
2. **Yapılan Değişiklikler**: Bullet list of changes
3. **Teknik Detaylar**: Implementation notes (optional)
4. **Test Notları**: How to verify the changes

Use professional but accessible language.
```

### Implementing Prompt Support

Your integration inherits prompt methods from `TaskManagementBase`:

```python
class MyTrackerIntegration(TaskManagementBase):
    name = "my_tracker"

    # These methods are inherited:
    # - get_prompt(name): Get prompt (user-exported or builtin)
    # - has_user_prompt(name): Check if user has custom prompt
    # - get_user_prompt(name): Get only user-exported prompt
    # - export_prompts(): Export prompts for customization

    def _get_builtin_prompt(self, prompt_name: str) -> str:
        """Return built-in prompts for this integration."""
        prompts = {
            "issue_title": """Generate a clear issue title...""",
            "issue_description": """Generate a detailed description..."""
        }
        return prompts.get(prompt_name)
```

### Issue Language Configuration

Users can set their preferred language in config:

```yaml
integrations:
  jira:
    enabled: true
    site: https://company.atlassian.net
    project_key: PROJ
    issue_language: tr  # Turkish
```

Supported language codes:
- `en` - English (default)
- `tr` - Turkish
- `de` - German
- `fr` - French
- `es` - Spanish
- `pt` - Portuguese
- `it` - Italian
- `ru` - Russian
- `zh` - Chinese
- `ja` - Japanese
- `ko` - Korean

When `issue_language` is set, RedGit:
1. Uses custom prompts if available
2. Instructs LLM to generate `issue_title` and `issue_description` in that language
3. Keeps `commit_title` and `commit_body` in English (git convention)

### Exporting Prompts for Customization

Users can export your integration's prompts to customize them:

```python
# In your integration
class MyTrackerIntegration(TaskManagementBase):
    def export_prompts(self, target_dir: str = None) -> list:
        """Export prompts for user customization."""
        from pathlib import Path
        from ..core.config import RETGIT_DIR

        target = Path(target_dir) if target_dir else RETGIT_DIR / "prompts" / "integrations" / self.name
        target.mkdir(parents=True, exist_ok=True)

        exported = []
        for prompt_name in ["issue_title", "issue_description"]:
            content = self._get_builtin_prompt(prompt_name)
            if content:
                path = target / f"{prompt_name}.md"
                path.write_text(content, encoding="utf-8")
                exported.append(str(path))

        return exported
```

Users can then run:
```bash
# Export Jira prompts for customization
rg integration prompts jira --export

# Creates:
# .redgit/prompts/integrations/jira/issue_title.md
# .redgit/prompts/integrations/jira/issue_description.md
```

### Verbose Mode for Debugging

Use verbose mode to verify prompts are being used:

```bash
rg propose -v -d -n
```

Output shows:
```
═══ Integration Prompts ═══
✓ Using USER-EXPORTED prompts for issue generation
  issue_title: .redgit/prompts/integrations/jira/issue_title.md
  issue_description: .redgit/prompts/integrations/jira/issue_description.md

═══ Detailed Analysis: Group 1/3 ═══
Prompt Source: integration prompts
╭─── LLM Prompt (Group 1) ───╮
│ ...your custom prompt...   │
╰────────────────────────────╯
```

---

## Publishing Your Integration

Once you've created and tested your integration, you can publish it so others can install it with `rg install`.

### Option 1: Publish to Your Own GitHub Repository

1. **Create a GitHub repository** for your integration:

   ```bash
   # Navigate to your integration folder
   cd .redgit/integrations/my_tracker

   # Initialize git
   git init
   git add .
   git commit -m "Initial commit"

   # Create repo on GitHub and push
   git remote add origin https://github.com/yourusername/redgit-my-tracker.git
   git push -u origin main
   ```

2. **Add an `index.json`** file to the root:

   ```json
   {
     "name": "my_tracker",
     "version": "1.0.0",
     "description": "My custom task tracker integration",
     "type": "task_management",
     "author": "Your Name",
     "homepage": "https://github.com/yourusername/redgit-my-tracker"
   }
   ```

3. **Others can now install it**:

   ```bash
   # Install from GitHub URL
   rg install github:yourusername/redgit-my-tracker

   # Or with full URL
   rg install https://github.com/yourusername/redgit-my-tracker
   ```

### Option 2: Submit to Official RedGit Tap

To make your integration available in the official tap (`rg install my_tracker`):

1. **Fork** [github.com/ertiz82/redgit-tap](https://github.com/ertiz82/redgit-tap)

2. **Add your integration** to the `integrations/` folder:

   ```
   redgit-tap/
   └── integrations/
       └── my_tracker/
           ├── __init__.py
           ├── commands.py
           ├── install_schema.json
           └── README.md
   ```

3. **Update `index.json`** in the root to include your integration:

   ```json
   {
     "integrations": {
       "my_tracker": {
         "name": "My Tracker",
         "version": "1.0.0",
         "description": "Custom task tracker integration",
         "type": "task_management",
         "path": "integrations/my_tracker"
       }
     }
   }
   ```

4. **Submit a Pull Request**

Once merged, users can install with:

```bash
rg install my_tracker
```

### Repository Structure for Publishing

```
redgit-my-tracker/
├── __init__.py           # Integration class (required)
├── commands.py           # CLI commands (optional)
├── install_schema.json   # Install wizard config (recommended)
├── README.md             # Documentation (recommended)
├── index.json            # Package metadata (required for tap)
└── prompts/              # AI prompts (optional)
    └── analyze.txt
```

### Versioning

Use semantic versioning in your `index.json`:

```json
{
  "version": "1.0.0"
}
```

Users can install specific versions:

```bash
rg install my_tracker@1.0.0
rg install my_tracker@latest
```

---

## See Also

- [RedGit Tap](../tap.md) - Community integrations repository
- [Integrations Overview](index.md) - All available integrations